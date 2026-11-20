#!/usr/bin/env python3
"""Serve the SMART data Ceph already collects as Prometheus metrics.

Ceph's devicehealth module has every OSD run `smartctl -x --json` on its disk
once a day and keeps the results. This reads the newest result for each disk
(`ceph device get-health-metrics`) and serves it under the metric names
smartctl_exporter uses, so its dashboards and queries work. Nothing runs on
the hypervisors. Only disks that back a Ceph daemon are covered, and values
change once a day; `ceph_smart_sample_timestamp_seconds` says how old each is.

`instance` is set to the disk's host, so scrape with honorLabels.
Run with --once to print the metrics and exit.
"""

import calendar
import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("PORT", "9633"))
REFRESH_SECONDS = int(os.environ.get("REFRESH_SECONDS", "21600"))
CEPH_TIMEOUT = int(os.environ.get("CEPH_TIMEOUT_SECONDS", "120"))

ATTRIBUTE_FLAGS = ["prefailure", "updated_online", "performance", "error_rate", "event_count", "auto_keep"]
ERROR_COUNTERS = {
    "errors_corrected_by_rereads_rewrites": "errors_corrected_by_rereads_rewrites",
    "errors_corrected_by_eccfast": "errors_corrected_by_eccfast",
    "errors_corrected_by_eccdelayed": "errors_corrected_by_eccdelayed",
    "total_uncorrected_errors": "total_uncorrected_errors",
}

state = {"body": b""}
errors_total = 0


def ceph(*args):
    out = subprocess.run(
        ["ceph", *args, "--format", "json"],
        check=True, capture_output=True, timeout=CEPH_TIMEOUT,
    ).stdout
    return json.loads(out)


def number(value):
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    return None


class Metrics:
    def __init__(self):
        self.families = {}

    def add(self, name, kind, help_text, value, **labels):
        value = number(value)
        if value is None:
            return
        family = self.families.setdefault(name, (kind, help_text, []))
        rendered = ",".join(
            '%s="%s"' % (k, str(v).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " "))
            for k, v in labels.items()
        )
        family[2].append("%s{%s} %s" % (name, rendered, repr(value)) if rendered else "%s %s" % (name, repr(value)))

    def render(self):
        lines = []
        for name, (kind, help_text, samples) in sorted(self.families.items()):
            lines.append("# HELP %s %s" % (name, help_text))
            lines.append("# TYPE %s %s" % (name, kind))
            lines.extend(samples)
        return ("\n".join(lines) + "\n").encode()


def device_metrics(m, dev, sample_key, smart):
    """Add one disk's metrics. `dev` is a `ceph device ls` entry."""
    location = (dev.get("location") or [{}])[0]
    base = {"instance": (location.get("host") or "unknown").lower(), "device": location.get("dev") or dev["devid"]}
    info = smart.get("device") or {}
    get = lambda key: str(smart.get(key, "") or "")  # noqa: E731

    m.add(
        "smartctl_device", "gauge", "Device info", 1, **base,
        interface=info.get("type", ""), protocol=info.get("protocol", ""),
        model_family=smart.get("model_family", "unknown"),
        model_name=get("model_name") or get("scsi_model_name") or "unknown",
        serial_number=get("serial_number"),
        firmware_version=get("firmware_version"),
        form_factor=str((smart.get("form_factor") or {}).get("name", "")),
        scsi_vendor=get("scsi_vendor"), scsi_product=get("scsi_product"),
        scsi_revision=get("scsi_revision"), scsi_version=get("scsi_version"),
        devid=dev["devid"], ceph_daemon=",".join(dev.get("daemons") or []),
    )
    m.add(
        "ceph_smart_sample_timestamp_seconds", "gauge",
        "When Ceph took this disk's SMART reading (unix time)",
        calendar.timegm(time.strptime(sample_key, "%Y%m%d-%H%M%S")), **base,
    )
    m.add("smartctl_device_smart_status", "gauge", "General smart status (1 = passed)",
          (smart.get("smart_status") or {}).get("passed"), **base)
    m.add("smartctl_device_smartctl_exit_status", "gauge", "Exit status of smartctl on device",
          (smart.get("smartctl") or {}).get("exit_status"), **base)
    for key, value in (smart.get("temperature") or {}).items():
        m.add("smartctl_device_temperature", "gauge", "Device temperature celsius",
              value, **base, temperature_type=key)
    power_on = smart.get("power_on_time")
    if power_on:
        m.add("smartctl_device_power_on_seconds", "counter", "Device power on seconds",
              power_on.get("hours", 0) * 3600 + power_on.get("minutes", 0) * 60, **base)
    cycles = smart.get("power_cycle_count")
    if cycles is None:
        cycles = (smart.get("scsi_start_stop_cycle_counter") or {}).get("accumulated_start_stop_cycles")
    m.add("smartctl_device_power_cycle_count", "counter", "Device power cycle count", cycles, **base)
    if smart.get("rotation_rate"):
        m.add("smartctl_device_rotation_rate", "gauge", "Device rotation rate", smart["rotation_rate"], **base)
    capacity = smart.get("user_capacity") or {}
    m.add("smartctl_device_capacity_bytes", "gauge", "Device capacity in bytes", capacity.get("bytes"), **base)
    m.add("smartctl_device_capacity_blocks", "gauge", "Device capacity in blocks", capacity.get("blocks"), **base)

    # ATA attribute table
    for attr in (smart.get("ata_smart_attributes") or {}).get("table") or []:
        flags = attr.get("flags") or {}
        labels = dict(
            base,
            attribute_name=str(attr.get("name", "")).strip(),
            attribute_flags_short=str(flags.get("string", "")).strip(),
            attribute_flags_long=",".join(f for f in ATTRIBUTE_FLAGS if flags.get(f)),
            attribute_id=attr.get("id", ""),
        )
        values = {"value": attr.get("value"), "worst": attr.get("worst"), "thresh": attr.get("thresh"),
                  "raw": (attr.get("raw") or {}).get("value")}
        for value_type, value in values.items():
            m.add("smartctl_device_attribute", "gauge", "Device attributes",
                  value, **labels, attribute_value_type=value_type)

    # SCSI / SAS counters
    m.add("smartctl_scsi_grown_defect_list", "counter", "Device SCSI grown defect list counter",
          smart.get("scsi_grown_defect_list"), **base)
    m.add("smartctl_scsi_percentage_used_endurance_indicator", "gauge",
          "Device SCSI percentage used endurance indicator",
          smart.get("scsi_percentage_used_endurance_indicator"), **base)
    error_log = smart.get("scsi_error_counter_log") or {}
    for op in ("read", "write", "verify"):
        for key, suffix in ERROR_COUNTERS.items():
            m.add("smartctl_%s_%s" % (op, suffix), "counter", "%s %s" % (op.capitalize(), suffix.replace("_", " ")),
                  (error_log.get(op) or {}).get(key), **base)


def collect():
    global errors_total
    started = time.time()
    m = Metrics()
    devices = ceph("device", "ls")
    exported = 0
    for dev in devices:
        try:
            samples = ceph("device", "get-health-metrics", dev["devid"])
            # Newest reading that actually holds smartctl output (a failed scrape stores an error stub).
            usable = [k for k in sorted(samples) if isinstance(samples[k], dict) and "smartctl" in samples[k]]
            if not usable:
                continue
            device_metrics(m, dev, usable[-1], samples[usable[-1]])
            exported += 1
        except Exception as exc:  # one bad disk must not hide the rest
            errors_total += 1
            print("device %s: %s" % (dev.get("devid"), exc), file=sys.stderr, flush=True)
    m.add("ceph_smart_exporter_devices", "gauge", "Disks Ceph knows about", len(devices))
    m.add("ceph_smart_exporter_devices_exported", "gauge", "Disks with a usable SMART reading", exported)
    m.add("ceph_smart_exporter_last_refresh_timestamp_seconds", "gauge", "Last successful read from Ceph", time.time())
    m.add("ceph_smart_exporter_refresh_duration_seconds", "gauge", "How long the last read took", time.time() - started)
    m.add("ceph_smart_exporter_errors_total", "counter", "Failed reads since start", errors_total)
    return m.render(), exported, len(devices)


def refresh_forever():
    global errors_total
    while True:
        delay = REFRESH_SECONDS
        try:
            body, exported, total = collect()
            state["body"] = body
            print("refreshed: %d of %d disks" % (exported, total), flush=True)
        except Exception as exc:
            errors_total += 1
            delay = min(REFRESH_SECONDS, 300)  # Ceph unreachable: keep the old data, retry soon
            print("refresh failed: %s" % exc, file=sys.stderr, flush=True)
        time.sleep(delay)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/healthz":
            self.reply(200, b"ok\n")
        elif self.path.startswith("/metrics"):
            self.reply(200, state["body"])
        else:
            self.reply(404, b"not found\n")

    def reply(self, code, body):
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    if "--once" in sys.argv:
        sys.stdout.buffer.write(collect()[0])
        sys.exit(0)
    threading.Thread(target=refresh_forever, daemon=True).start()
    ThreadingHTTPServer(("", PORT), Handler).serve_forever()

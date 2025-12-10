---
description: Validate recyclarr.yml config against official documentation
allowed-tools: Read, WebFetch, WebSearch, Grep, Glob
---

# Recyclarr Configuration Validator

You are validating a recyclarr.yml configuration file against the official Recyclarr documentation.

## Configuration File Location

The recyclarr.yml config is located at:
`kubernetes/apps/media/recyclarr/app/config/recyclarr.yml`

## Validation Process

### Step 1: Read the Current Configuration
First, read the recyclarr.yml file to understand the current configuration.

### Step 2: Search Official Documentation
Use WebSearch and WebFetch to search the following Recyclarr documentation sources for the latest information:

**Primary Documentation URLs:**
- Config Reference: https://recyclarr.dev/wiki/yaml/config-reference/
- Quality Definitions: https://recyclarr.dev/wiki/yaml/config-reference/quality-definition/
- Custom Formats: https://recyclarr.dev/wiki/yaml/config-reference/custom-formats/
- Media Naming: https://recyclarr.dev/wiki/yaml/config-reference/media-naming/
- Quality Profiles: https://recyclarr.dev/wiki/yaml/config-reference/quality-profiles/
- Include Templates: https://recyclarr.dev/wiki/yaml/config-reference/include/

**TRaSH Guides Integration:**
- Sonarr Templates: https://recyclarr.dev/wiki/guide-configs/sonarr/
- Radarr Templates: https://recyclarr.dev/wiki/guide-configs/radarr/

### Step 3: Validation Checklist

For each instance (sonarr, sonarr-uhd, radarr, radarr-uhd), validate:

1. **Schema Compliance**
   - Verify the YAML structure matches the official schema
   - Check for deprecated configuration options

2. **Template Validation**
   - Verify all `include.template` values exist in official TRaSH guides
   - Cross-reference template names with: https://recyclarr.dev/wiki/guide-configs/

3. **Custom Format Trash IDs**
   - Verify all `trash_ids` are valid and current
   - Search for any deprecated or renamed trash IDs
   - Check for newer recommended custom formats

4. **Quality Definition Types**
   - Verify `quality_definition.type` values are valid (series, movie, anime)

5. **Media Naming**
   - Validate `media_naming` options against current documentation
   - Check for any deprecated naming formats

6. **Quality Profile Names**
   - Verify quality profile names match those created by templates
   - Common profiles: WEB-1080p, WEB-2160p, HD Bluray + WEB, UHD Bluray + WEB

7. **API Configuration**
   - Verify base_url format is correct
   - Check that env_var syntax is valid

### Step 4: Search for Updates

Use WebSearch to find:
```
site:recyclarr.dev "breaking changes" OR "deprecated" OR "new feature" 2024 2025
```

Search for recent changes that might affect the configuration.

### Step 5: Generate Report

Provide a detailed report with:

1. **Configuration Summary**
   - List all configured instances
   - Templates being used
   - Custom formats applied

2. **Validation Results**
   - Green checkmarks for valid items
   - Warnings for potentially outdated items
   - Errors for invalid configurations

3. **Recommendations**
   - Suggest any newer templates available
   - Recommend additional custom formats if beneficial
   - Note any configuration improvements

4. **Documentation Links**
   - Provide direct links to relevant documentation for any issues found

## Output Format

```markdown
## Recyclarr Configuration Validation Report

### Instances Found
- [ ] sonarr (1080p)
- [ ] sonarr-uhd (4K)
- [ ] radarr (HD)
- [ ] radarr-uhd (4K)

### Template Validation
| Instance | Template | Status | Notes |
|----------|----------|--------|-------|
| ... | ... | ... | ... |

### Custom Format Validation
| Trash ID | Name | Status | Notes |
|----------|------|--------|-------|
| ... | ... | ... | ... |

### Issues Found
1. [SEVERITY] Description - Link to docs

### Recommendations
1. Description - Link to docs

### Documentation References
- [Link description](url)
```

## Important Notes

- Always use the most recent documentation from recyclarr.dev
- The TRaSH Guides are updated frequently - verify trash_ids are current
- Check for any v4 vs v5 Sonarr/Radarr compatibility notes
- Media naming options differ between Sonarr and Radarr

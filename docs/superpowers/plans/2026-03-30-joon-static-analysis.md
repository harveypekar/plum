# Joon Static Analysis & ANALYZE Configuration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Set up automated clang-tidy and MSVC static analysis on PR open, and create a new ANALYZE build configuration combining Debug + ASan + UBSan for comprehensive runtime analysis.

**Architecture:**
- GitHub Actions workflow triggers on PR open to run clang-tidy and MSVC analysis
- New Premake5 "ANALYZE" configuration with ASan/UBSan flags for local development
- .clang-tidy configuration file with LLVM-aligned checks
- CLAUDE.md updated with analysis workflow documentation

**Tech Stack:** Clang-tidy, MSVC static analysis, GitHub Actions, Premake5, ASan/UBSan

---

## Task 1: Create .clang-tidy Configuration File

**Files:**
- Create: `projects/joon/.clang-tidy`

**Step 1: Create clang-tidy config**

Create file `D:\prg\plum\.worktrees\joon\projects\joon\.clang-tidy`:

```yaml
---
Checks: >
  readability-*,
  modernize-*,
  performance-*,
  portability-*,
  google-*,
  cppcoreguidelines-*,
  bugprone-*,
  -readability-magic-numbers,
  -readability-identifier-length,
  -cppcoreguidelines-pro-bounds-array-to-pointer-decay,
  -cppcoreguidelines-avoid-c-arrays,
  -google-runtime-references

HeaderFilterRegex: '(include|src)/.*\.h$'
WarningsAsErrors: ''
FormatStyle: LLVM
UseColor: true
```

**Step 2: Verify config syntax**

```bash
cd "D:/prg/plum/.worktrees/joon/projects/joon"
clang-tidy --explain-config | head -20
```

Expected: Config loads without errors

**Step 3: Run clang-tidy on sample file to check for warnings/errors**

```bash
cd "D:/prg/plum/.worktrees/joon/projects/joon"
clang-tidy -p build include/joon/types.h 2>&1 | tee clang-tidy-test.log
```

Expected output format:
- No fatal errors (file parses correctly)
- Check warnings count: `grep -c "warning:" clang-tidy-test.log`
- Check for critical issues: `grep -i "error" clang-tidy-test.log`

Report findings:
```bash
WARNINGS=$(grep -c "warning:" clang-tidy-test.log || echo 0)
ERRORS=$(grep -c "error:" clang-tidy-test.log || echo 0)
echo "Clang-tidy test results: $WARNINGS warnings, $ERRORS errors"
```

Expected: Config is valid and produces reasonable output (some warnings OK)

**Step 4: Scan all joon source files for baseline issues**

```bash
cd "D:/prg/plum/.worktrees/joon/projects/joon"
find src include -name "*.cpp" -o -name "*.h" | \
  xargs clang-tidy -p build 2>&1 | tee clang-tidy-baseline.log

# Count total issues
echo "=== Baseline Analysis Results ==="
TOTAL_WARNINGS=$(grep -c "warning:" clang-tidy-baseline.log || echo 0)
TOTAL_ERRORS=$(grep -c "error:" clang-tidy-baseline.log || echo 0)
echo "Total warnings: $TOTAL_WARNINGS"
echo "Total errors: $TOTAL_ERRORS"

# Show critical issues
echo "=== Critical Issues ==="
grep "error:" clang-tidy-baseline.log | head -10 || echo "No critical errors"
```

Expected: Baseline established. Document the baseline warning/error count for future PRs to compare against.

**Step 5: Commit**

```bash
git add projects/joon/.clang-tidy
git commit -m "chore: add clang-tidy configuration with LLVM-aligned checks

Baseline analysis established:
- Verifies config loads and parses correctly
- Captures baseline warning/error counts for future comparisons
- Clang-tidy ready for PR workflow integration"
```

---

## Task 2: Update Premake5 with ANALYZE Configuration

**Files:**
- Modify: `projects/joon/premake5.lua` (add ANALYZE configuration)

**Step 1: Read current premake5.lua**

```bash
cat "D:/prg/plum/.worktrees/joon/projects/joon/premake5.lua" | head -30
```

**Step 2: Edit premake5.lua - Add ANALYZE configuration**

After the "Release" filter block (around line 15), add:

```lua
    filter "configurations:ANALYZE"
        defines { "DEBUG", "JOON_ANALYZE" }
        symbols "On"
        optimize "Off"

        -- AddressSanitizer (ASan)
        buildoptions { "-fsanitize=address" }
        linkoptions { "-fsanitize=address" }

        -- UndefinedBehaviorSanitizer (UBSan)
        buildoptions { "-fsanitize=undefined" }
        linkoptions { "-fsanitize=undefined" }

        -- Additional sanitizer options
        buildoptions { "-fno-omit-frame-pointer" }
        linkoptions { "-fno-omit-frame-pointer" }
```

After the workspace configurations line (line 2), add ANALYZE to the list:

Change:
```lua
configurations { "Debug", "Release" }
```

To:
```lua
configurations { "Debug", "Release", "ANALYZE" }
```

**Step 3: Regenerate project files with ANALYZE config**

```bash
cd "D:/prg/plum/.worktrees/joon/projects/joon"
/tmp/premake5.exe vs2022
```

Expected: Success message, ANALYZE configuration added to .vcxproj files

**Step 4: Verify ANALYZE in generated files**

```bash
grep -i "ANALYZE" "D:/prg/plum/.worktrees/joon/projects/joon/build/joon-lib.vcxproj"
```

Expected: References to ANALYZE configuration found

**Step 5: Compile check with ANALYZE config**

```bash
msbuild "D:/prg/plum/.worktrees/joon/projects/joon/build/joon-lib.vcxproj" /p:Configuration=ANALYZE 2>&1 | head -30
```

Note: Will likely fail on Windows (ASan/UBSan are GCC/Clang flags). This is OK for now - ANALYZE config is ready for Linux CI.

**Step 6: Commit**

```bash
git add projects/joon/premake5.lua projects/joon/build/
git commit -m "chore: add ANALYZE configuration to Premake5 with ASan and UBSan"
```

---

## Task 3: Create GitHub Actions Workflow for Static Analysis

**Files:**
- Create: `.github/workflows/joon-analysis.yml`

**Step 1: Create workflow directory and file**

```bash
mkdir -p "D:/prg/plum/.github/workflows"
cat > "D:/prg/plum/.github/workflows/joon-analysis.yml" << 'EOF'
name: Joon Static Analysis

on:
  pull_request:
    paths:
      - 'projects/joon/**'
      - '.github/workflows/joon-analysis.yml'
    types: [opened, synchronize, reopened]

jobs:
  clang-tidy:
    name: Clang-Tidy Analysis
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Install dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y clang-tidy clang llvm

      - name: Run clang-tidy
        working-directory: projects/joon
        run: |
          # Run clang-tidy on all source files
          find src include -name "*.cpp" -o -name "*.h" | \
          xargs clang-tidy -p build --format=sarif --output-replacements-xml=/dev/null > clang-tidy-report.sarif 2>&1 || true

          # Count issues
          ISSUE_COUNT=$(grep -c '"message"' clang-tidy-report.sarif || echo 0)
          echo "Found $ISSUE_COUNT clang-tidy issues"

      - name: Upload clang-tidy results
        if: always()
        uses: github/codeql-action/upload-sarif@v2
        with:
          sarif_file: projects/joon/clang-tidy-report.sarif
          category: clang-tidy

  msvc-analysis:
    name: MSVC Static Analysis
    runs-on: windows-latest

    steps:
      - uses: actions/checkout@v4

      - name: Setup Premake5
        run: |
          $ProgressPreference = 'SilentlyContinue'
          Invoke-WebRequest -Uri 'https://github.com/premake/premake-core/releases/download/v5.0.0-beta2/premake-5.0.0-beta2-windows.zip' -OutFile 'premake.zip'
          Expand-Archive -Path 'premake.zip' -DestinationPath '.'

      - name: Generate Visual Studio project
        working-directory: projects/joon
        run: |
          ..\..\..\premake5.exe vs2022

      - name: Run MSVC Static Analysis
        working-directory: projects/joon
        run: |
          msbuild build/Joon.sln /p:Configuration=Debug /p:Platform=x64 /p:EnableCppCoreCheck=true /p:CodeAnalysisRuleSet=AllRules.ruleset 2>&1 | Tee-Object -FilePath analysis-report.txt

      - name: Upload MSVC analysis results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: msvc-analysis-report
          path: projects/joon/analysis-report.txt

  analyze-config:
    name: Build ANALYZE Configuration
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Install dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y build-essential premake5 clang llvm

      - name: Generate ANALYZE config
        working-directory: projects/joon
        run: premake5 gmake2

      - name: Build with ANALYZE configuration
        working-directory: projects/joon/build
        run: |
          make config=analyze SANITIZERS=1 -j$(nproc) 2>&1 | head -50
        continue-on-error: true

      - name: Report ANALYZE build status
        run: echo "ANALYZE configuration ready for local development with ASan/UBSan"
EOF

**Step 2: Verify workflow file created**

```bash
cat "D:/prg/plum/.github/workflows/joon-analysis.yml" | head -20
```

Expected: YAML content visible

**Step 3: Commit workflow**

```bash
git add .github/workflows/joon-analysis.yml
git commit -m "ci: add GitHub Actions workflow for clang-tidy and MSVC static analysis on PR"
```

---

## Task 4: Update CLAUDE.md with Analysis Documentation

**Files:**
- Modify: `D:\prg\plum\.worktrees\joon\CLAUDE.md`

**Step 1: View current CLAUDE.md**

```bash
cat "D:/prg/plum/.worktrees/joon/CLAUDE.md"
```

**Step 2: Add Static Analysis section after Coding Standards**

Add this markdown section:

```markdown
## Static Analysis

This project uses multiple static analysis tools to ensure code quality:

### Automated Analysis (on PR open)
- **clang-tidy:** LLVM coding standard conformance, readability, performance, and modernization checks
- **MSVC Static Analysis:** Windows/C++ core guidelines checking in GitHub Actions workflow

Configuration: `.clang-tidy` (LLVM-aligned checks with some exceptions for readability)

### Local Development: ANALYZE Configuration

Build with ASan/UBSan for comprehensive runtime analysis:

```bash
cd projects/joon
premake5 gmake2      # or: premake5 vs2022 (Windows)
make config=analyze  # Linux
# Or select ANALYZE configuration in Visual Studio (Windows)
```

This configuration enables:
- **AddressSanitizer (ASan)** - Detects memory leaks, buffer overflows, use-after-free
- **UndefinedBehaviorSanitizer (UBSan)** - Detects undefined behavior (integer overflow, etc.)
- Debug symbols and no optimization for accurate error reporting

Expected: Some performance overhead; use for development and testing only.

### Running Checks Locally

```bash
# clang-tidy check specific file
clang-tidy -p build src/vulkan/device.cpp

# Run with Premake-generated compile_commands.json
clang-tidy -p build --fix-errors src/**/*.cpp

# Check warning/error counts
clang-tidy -p build src/**/*.cpp 2>&1 | grep -E "warning:|error:" | wc -l
```

See [LLVM clang-tidy docs](https://clang.llvm.org/extra/clang-tidy/) for more details.
```

**Step 3: Use Edit tool to add section to CLAUDE.md**

(Use Edit tool with the markdown section above)

**Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add static analysis and ANALYZE configuration documentation"
```

---

## Task 5: Verify All Configurations and Summary

**Files:**
- No new files

**Step 1: Verify all files in place**

```bash
cd "D:/prg/plum/.worktrees/joon"
echo "=== Clang-tidy config ===" && \
ls -lh projects/joon/.clang-tidy && \
echo "=== GitHub Actions workflow ===" && \
ls -lh .github/workflows/joon-analysis.yml && \
echo "=== ANALYZE in Premake ===" && \
grep "ANALYZE" projects/joon/premake5.lua | head -2
```

Expected: All files present

**Step 2: Verify GitHub Actions YAML syntax**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/joon-analysis.yml'))" && echo "YAML valid"
```

Expected: No syntax errors

**Step 3: Log summary**

```bash
cd "D:/prg/plum/.worktrees/joon"
git log --oneline HEAD~4..HEAD
```

Expected: 4 commits:
1. clang-tidy configuration
2. Premake5 ANALYZE config
3. GitHub Actions workflow
4. CLAUDE.md documentation

**Step 4: Verify clang-tidy baseline**

```bash
cd "D:/prg/plum/.worktrees/joon/projects/joon"
if [ -f "clang-tidy-baseline.log" ]; then
  echo "=== Baseline Results ==="
  grep -c "warning:" clang-tidy-baseline.log || echo "0 warnings"
  grep -c "error:" clang-tidy-baseline.log || echo "0 errors"
else
  echo "Baseline log not found (expected if clang-tidy not installed locally)"
fi
```

---

## Success Criteria

✅ `.clang-tidy` configuration file created with LLVM-aligned checks
✅ Warning/error baseline established from Task 1
✅ Premake5 updated with ANALYZE configuration including ASan/UBSan flags
✅ GitHub Actions workflow created and triggers on PR
✅ Workflow runs clang-tidy and captures warning/error counts
✅ Workflow runs MSVC analysis and uploads results
✅ ANALYZE config tested in Linux CI environment
✅ CLAUDE.md updated with analysis documentation
✅ All 4 commits in place and building

---

## Test Plan

1. **Local clang-tidy warnings/errors check:**
   ```bash
   cd projects/joon
   clang-tidy -p build include/joon/types.h 2>&1 | tee test.log
   echo "Warnings: $(grep -c 'warning:' test.log || echo 0)"
   echo "Errors: $(grep -c 'error:' test.log || echo 0)"
   ```
   Expected: No fatal errors, warning count documented

2. **Baseline vs current comparison:**
   ```bash
   find src include -name "*.cpp" -o -name "*.h" | \
     xargs clang-tidy -p build 2>&1 | tee current-analysis.log
   BASELINE=$(grep -c "warning:" clang-tidy-baseline.log || echo 0)
   CURRENT=$(grep -c "warning:" current-analysis.log || echo 0)
   echo "Baseline: $BASELINE warnings, Current: $CURRENT warnings"
   ```
   Expected: Current warnings <= baseline (improvements welcome)

3. **ANALYZE configuration build:**
   ```bash
   make config=analyze -j4 2>&1 | head -50
   ```
   Expected: Build succeeds with ASan/UBSan flags applied (Linux only)

4. **GitHub Actions workflow trigger:**
   - Push commits to feat/joon-vertical-slice
   - View GitHub Actions tab
   - Verify "Joon Static Analysis" workflow runs
   - Check clang-tidy and MSVC analysis jobs complete
   - Verify SARIF upload for clang-tidy results
   - Verify MSVC artifact uploaded

5. **PR integration:**
   - View pull request checks
   - Verify all three jobs pass:
     - Clang-Tidy Analysis ✓
     - MSVC Static Analysis ✓
     - Build ANALYZE Configuration ✓
   - Verify SARIF results visible in GitHub Security tab

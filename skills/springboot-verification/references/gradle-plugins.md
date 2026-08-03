# Gradle Plugin Reference for Spring Boot Verification

This reference covers the Gradle plugins used in the Spring Boot Verification Loop, including configuration snippets, common options, and troubleshooting tips.

---

## Table of Contents

1. [SpotBugs](#spotbugs)
2. [PMD](#pmd)
3. [Checkstyle](#checkstyle)
4. [JaCoCo](#jacoco)
5. [OWASP Dependency-Check](#owasp-dependency-check)
6. [Spotless](#spotless)
7. [Test Logging](#test-logging)

---

## SpotBugs

### Minimal Configuration (Groovy DSL)

```groovy
plugins {
    id 'com.github.spotbugs' version '6.0.18'
}

spotbugs {
    effort = 'max'
    reportLevel = 'low'
    ignoreFailures = false
    includeTests = false
}

tasks.withType(com.github.spotbugs.snom.SpotBugsTask).configureEach {
    reports {
        html {
            required = true
            outputLocation = file("$buildDir/reports/spotbugs/main.html")
        }
        xml {
            required = true
            outputLocation = file("$buildDir/reports/spotbugs/main.xml")
        }
    }
}
```

### Minimal Configuration (Kotlin DSL)

```kotlin
plugins {
    id("com.github.spotbugs") version "6.0.18"
}

spotbugs {
    effort.set(com.github.spotbugs.snom.Effort.MAX)
    reportLevel.set(com.github.spotbugs.snom.Confidence.LOW)
    ignoreFailures.set(false)
}

tasks.withType<com.github.spotbugs.snom.SpotBugsTask>().configureEach {
    reports {
        create("html") {
            required.set(true)
            outputLocation.set(file("$buildDir/reports/spotbugs/main.html"))
        }
    }
}
```

### Exclusion Filter

```xml
<!-- spotbugs-exclude.xml (same as Maven) -->
<FindBugsFilter>
    <Match>
        <Package name="~com\.example\.generated\..*"/>
    </Match>
</FindBugsFilter>
```

```groovy
spotbugs {
    excludeFilter = file('spotbugs-exclude.xml')
}
```

### Command

```bash
./gradlew spotbugsMain          # Check main source
./gradlew spotbugsTest          # Check test source
./gradlew spotbugsCheck         # Check all
```

---

## PMD

### Minimal Configuration (Groovy DSL)

```groovy
plugins {
    id 'pmd'
}

pmd {
    consoleOutput = true
    toolVersion = '7.3.0'
    rulesMinimumPriority = 5
    ignoreFailures = false
    ruleSets = [
        'category/java/bestpractices.xml',
        'category/java/codestyle.xml',
        'category/java/design.xml',
        'category/java/errorprone.xml',
        'category/java/security.xml'
    ]
}

tasks.withType(Pmd).configureEach {
    reports {
        xml.required = true
        html.required = true
    }
}
```

### Custom Ruleset

```xml
<!-- pmd-ruleset.xml (same format as Maven) -->
<?xml version="1.0"?>
<ruleset name="Custom Ruleset"
    xmlns="http://pmd.sourceforge.net/ruleset/2.0.0">
    <description>Custom PMD rules for Spring Boot projects</description>
    <rule ref="category/java/bestpractices.xml"/>
    <rule ref="category/java/errorprone.xml"/>
    <rule ref="category/java/security.xml"/>
</ruleset>
```

```groovy
pmd {
    ruleSets = []
    ruleSetFiles = files('pmd-ruleset.xml')
}
```

### Command

```bash
./gradlew pmdMain              # Check main source
./gradlew pmdTest              # Check test source
./gradlew pmdCheck             # Check all
```

---

## Checkstyle

### Minimal Configuration (Groovy DSL)

```groovy
plugins {
    id 'checkstyle'
}

checkstyle {
    toolVersion = '10.17.0'
    configFile = file('checkstyle.xml')
    ignoreFailures = false
    maxWarnings = 0
}

tasks.withType(Checkstyle).configureEach {
    reports {
        xml.required = true
        html.required = true
    }
}
```

### Using Google Style

```groovy
checkstyle {
    configDirectory = file("$rootDir/config/checkstyle")
    // Place google_checks.xml in config/checkstyle/
}
```

### Command

```bash
./gradlew checkstyleMain       # Check main source
./gradlew checkstyleTest       # Check test source
./gradlew checkstyleCheck      # Check all
```

---

## JaCoCo

### Minimal Configuration (Groovy DSL)

```groovy
plugins {
    id 'jacoco'
}

jacoco {
    toolVersion = '0.8.12'
}

jacocoTestReport {
    dependsOn test
    reports {
        xml.required = true
        csv.required = true
        html.required = true
        html.outputLocation = layout.buildDirectory.dir('reports/jacoco/test/html')
    }
}

jacocoTestCoverageVerification {
    violationRules {
        rule {
            limit {
                counter = 'LINE'
                value = 'COVEREDRATIO'
                minimum = 0.80
            }
        }
        rule {
            limit {
                counter = 'BRANCH'
                value = 'COVEREDRATIO'
                minimum = 0.70
            }
        }
    }
}

test {
    finalizedBy jacocoTestReport
}

check {
    dependsOn jacocoTestCoverageVerification
}
```

### Exclusions

```groovy
jacocoTestCoverageVerification {
    violationRules {
        rule {
            element = 'CLASS'
            excludes = [
                'com.example.generated.*',
                'com.example.dto.*',
                'com.example.config.*',
                'com.example.Application'
            ]
            limit {
                counter = 'LINE'
                value = 'COVEREDRATIO'
                minimum = 0.80
            }
        }
    }
}
```

### Command

```bash
./gradlew test                      # Run tests
./gradlew jacocoTestReport          # Generate coverage report
./gradlew jacocoTestCoverageVerification  # Verify thresholds
```

### Report Location

```
build/reports/jacoco/test/html/index.html
build/reports/jacoco/test/jacocoTestReport.csv
build/reports/jacoco/test/jacocoTestReport.xml
```

---

## OWASP Dependency-Check

### Minimal Configuration (Groovy DSL)

```groovy
plugins {
    id 'org.owasp.dependencycheck' version '10.0.3'
}

dependencyCheck {
    failBuildOnCVSS = 7.0f
    suppressionFile = 'dependency-check-suppressions.xml'
    formats = ['HTML', 'JSON', 'SARIF']
    nvdApiKey = System.getenv('NVD_API_KEY')
}
```

### Command

```bash
./gradlew dependencyCheckAnalyze          # Run CVE check
./gradlew dependencyCheckAggregate        # Multi-module
```

### Report Location

```
build/reports/dependency-check-report.html
build/reports/dependency-check-report.json
```

---

## Spotless

### Minimal Configuration (Groovy DSL)

```groovy
plugins {
    id 'com.diffplug.spotless' version '6.25.0'
}

spotless {
    java {
        googleJavaFormat('1.19.2')
            .aosp()
            .reflowLongStrings()
        removeUnusedImports()
        trimTrailingWhitespace()
        endWithNewline()
    }

    format 'misc', {
        target '*.gradle', '*.md', '.gitignore'
        trimTrailingWhitespace()
        indentWithSpaces(4)
        endWithNewline()
    }
}
```

### Command

```bash
./gradlew spotlessCheck          # Check formatting
./gradlew spotlessApply          # Auto-format code
```

---

## Test Logging

### Enhanced Test Output

```groovy
test {
    useJUnitPlatform()

    testLogging {
        events 'passed', 'failed', 'skipped'
        showExceptions true
        showCauses true
        showStackTraces true
        exceptionFormat 'full'

        afterSuite { desc, result ->
            if (!desc.parent) {
                println "\nTest Results: ${result.resultType}"
                println "  ${result.testCount} tests"
                println "  ${result.successfulTestCount} passed"
                println "  ${result.failedTestCount} failed"
                println "  ${result.skippedTestCount} skipped"
            }
        }
    }
}
```

---

## Complete build.gradle Snippet

```groovy
plugins {
    id 'java'
    id 'org.springframework.boot' version '3.3.2'
    id 'io.spring.dependency-management' version '1.1.6'
    id 'com.github.spotbugs' version '6.0.18'
    id 'pmd'
    id 'checkstyle'
    id 'jacoco'
    id 'org.owasp.dependencycheck' version '10.0.3'
    id 'com.diffplug.spotless' version '6.25.0'
}

group = 'com.example'
version = '0.0.1-SNAPSHOT'

java {
    sourceCompatibility = JavaVersion.VERSION_21
}

// ... dependency and plugin configurations as shown above ...
```

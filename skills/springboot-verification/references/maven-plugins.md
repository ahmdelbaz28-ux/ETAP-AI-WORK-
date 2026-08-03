# Maven Plugin Reference for Spring Boot Verification

This reference covers the Maven plugins used in the Spring Boot Verification Loop, including configuration snippets, common options, and troubleshooting tips.

---

## Table of Contents

1. [SpotBugs](#spotbugs)
2. [PMD](#pmd)
3. [Checkstyle](#checkstyle)
4. [JaCoCo](#jacoco)
5. [OWASP Dependency-Check](#owasp-dependency-check)
6. [Spotless](#spotless)
7. [Maven Surefire](#maven-surefire)
8. [Maven Failsafe](#maven-failsafe)

---

## SpotBugs

Static analysis tool that finds bugs in Java code using bytecode analysis.

### Minimal Configuration

```xml
<plugin>
    <groupId>com.github.spotbugs</groupId>
    <artifactId>spotbugs-maven-plugin</artifactId>
    <version>4.8.6.0</version>
    <executions>
        <execution>
            <goals>
                <goal>check</goal>
            </goals>
        </execution>
    </executions>
    <configuration>
        <effort>Max</effort>
        <threshold>Low</threshold>
        <failOnError>true</failOnError>
        <includeTests>false</includeTests>
    </configuration>
</plugin>
```

### Common Options

| Option | Default | Description |
|--------|---------|-------------|
| `effort` | `Default` | Analysis effort: `Min`, `Default`, `Max` |
| `threshold` | `Medium` | Priority threshold: `High`, `Medium`, `Low` |
| `failOnError` | `true` | Fail the build on bugs |
| `includeTests` | `false` | Analyze test code |
| `excludeFilterFile` | — | Path to exclusion filter XML |

### Exclusion Filter Example

```xml
<!-- spotbugs-exclude.xml -->
<FindBugsFilter>
    <Match>
        <Package name="~com\.example\.generated\..*"/>
    </Match>
    <Match>
        <Bug pattern="EI_EXPOSE_REP2,MS_EXPOSE_REP"/>
    </Match>
</FindBugsFilter>
```

### Command

```bash
mvn spotbugs:check          # Check only (fails on bugs)
mvn spotbugs:spotbugs       # Generate report without failing
mvn spotbugs:gui            # Launch SpotBugs GUI
```

---

## PMD

Source code analyzer that finds common programming flaws.

### Minimal Configuration

```xml
<plugin>
    <groupId>org.apache.maven.plugins</groupId>
    <artifactId>maven-pmd-plugin</artifactId>
    <version>3.23.0</version>
    <executions>
        <execution>
            <goals>
                <goal>check</goal>
            </goals>
        </execution>
    </executions>
    <configuration>
        <failOnViolation>true</failOnViolation>
        <printFailingErrors>true</printFailingErrors>
        <includeTests>false</includeTests>
        <rulesets>
            <ruleset>/rulesets/java/quickstart.xml</ruleset>
        </rulesets>
    </configuration>
</plugin>
```

### Custom Ruleset Example

```xml
<!-- pmd-ruleset.xml -->
<?xml version="1.0"?>
<ruleset name="Custom Ruleset"
    xmlns="http://pmd.sourceforge.net/ruleset/2.0.0"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://pmd.sourceforge.net/ruleset/2.0.0 https://pmd.sourceforge.io/ruleset_2_0_0.xsd">

    <description>Custom PMD rules for Spring Boot projects</description>

    <rule ref="rulesets/java/quickstart.xml">
        <exclude name="LocalVariableCouldBeFinal"/>
        <exclude name="MethodArgumentCouldBeFinal"/>
    </rule>

    <rule ref="rulesets/java/design.xml">
        <exclude name="GodClass"/>
    </rule>

    <rule ref="rulesets/java/design.xml/TooManyMethods">
        <properties>
            <property name="maxmethods" value="15"/>
        </properties>
    </rule>
</ruleset>
```

### Command

```bash
mvn pmd:check               # Check only (fails on violations)
mvn pmd:pmd                  # Generate report
mvn pmd:cpd                  # Copy-paste detection
```

---

## Checkstyle

Code style and convention checker.

### Minimal Configuration

```xml
<plugin>
    <groupId>org.apache.maven.plugins</groupId>
    <artifactId>maven-checkstyle-plugin</artifactId>
    <version>3.4.0</version>
    <executions>
        <execution>
            <goals>
                <goal>check</goal>
            </goals>
        </execution>
    </executions>
    <configuration>
        <configLocation>google_checks.xml</configLocation>
        <failOnViolation>true</failOnViolation>
        <includeTestSourceDirectory>false</includeTestSourceDirectory>
    </configuration>
</plugin>
```

### Popular Config Locations

| Config | Description |
|--------|-------------|
| `google_checks.xml` | Google Java Style Guide |
| `sun_checks.xml` | Sun Java conventions |
| `checkstyle.xml` | Custom file in project root |

### Command

```bash
mvn checkstyle:check        # Check only (fails on violations)
mvn checkstyle:checkstyle   # Generate report
```

---

## JaCoCo

Java code coverage library.

### Minimal Configuration

```xml
<plugin>
    <groupId>org.jacoco</groupId>
    <artifactId>jacoco-maven-plugin</artifactId>
    <version>0.8.12</version>
    <executions>
        <execution>
            <id>prepare-agent</id>
            <goals>
                <goal>prepare-agent</goal>
            </goals>
        </execution>
        <execution>
            <id>report</id>
            <phase>test</phase>
            <goals>
                <goal>report</goal>
            </goals>
        </execution>
        <execution>
            <id>check</id>
            <goals>
                <goal>check</goal>
            </goals>
            <configuration>
                <rules>
                    <rule>
                        <element>BUNDLE</element>
                        <limits>
                            <limit>
                                <counter>LINE</counter>
                                <value>COVEREDRATIO</value>
                                <minimum>0.80</minimum>
                            </limit>
                            <limit>
                                <counter>BRANCH</counter>
                                <value>COVEREDRATIO</value>
                                <minimum>0.70</minimum>
                            </limit>
                        </limits>
                    </rule>
                </rules>
            </configuration>
        </execution>
    </executions>
</plugin>
```

### Coverage Thresholds

| Counter | Description | Typical Threshold |
|---------|-------------|-------------------|
| `LINE` | Line coverage | 80% |
| `BRANCH` | Branch coverage | 70% |
| `INSTRUCTION` | Bytecode instruction coverage | 80% |
| `METHOD` | Method entry coverage | 80% |
| `CLASS` | Class coverage | 90% |

### Exclusions

```xml
<configuration>
    <excludes>
        <exclude>**/generated/**</exclude>
        <exclude>**/dto/**</exclude>
        <exclude>**/config/**</exclude>
        <exclude>**/Application.*</exclude>
    </excludes>
</configuration>
```

### Command

```bash
mvn jacoco:prepare-agent     # Instrument classes
mvn test                      # Run tests with coverage
mvn jacoco:report             # Generate report
mvn jacoco:check              # Verify thresholds
```

### Report Location

```
target/site/jacoco/index.html
target/site/jacoco/jacoco.csv
target/site/jacoco/jacoco.xml
```

---

## OWASP Dependency-Check

Software composition analysis tool that detects known vulnerabilities.

### Minimal Configuration

```xml
<plugin>
    <groupId>org.owasp</groupId>
    <artifactId>dependency-check-maven</artifactId>
    <version>10.0.3</version>
    <executions>
        <execution>
            <goals>
                <goal>check</goal>
            </goals>
        </execution>
    </executions>
    <configuration>
        <failBuildOnCVSS>7</failBuildOnCVSS>
        <suppressionFile>dependency-check-suppressions.xml</suppressionFile>
        <nvdApiKey>${env.NVD_API_KEY}</nvdApiKey>
    </configuration>
</plugin>
```

### CVSS Thresholds

| CVSS Score | Severity | Recommended Action |
|------------|----------|-------------------|
| 0.0 | None | No action |
| 0.1–3.9 | Low | Review |
| 4.0–6.9 | Medium | Plan fix |
| 7.0–8.9 | High | Fix before release |
| 9.0–10.0 | Critical | Fix immediately |

### Suppression File Example

```xml
<!-- dependency-check-suppressions.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<suppressions xmlns="https://jeremylong.github.io/DependencyCheck/dependency-suppression.1.3.xsd">
    <suppress>
        <packageUrl regex="true">^pkg:maven/org\.example/library@.*$</packageUrl>
        <cve>CVE-2023-XXXXX</cve>
        <cve>CVE-2023-YYYYY</cve>
    </suppress>
</suppressions>
```

### Command

```bash
mvn org.owasp:dependency-check-maven:check    # Run CVE check
mvn org.owasp:dependency-check-maven:aggregate  # Multi-module
```

### Report Location

```
target/dependency-check-report.html
target/dependency-check-report.json
```

---

## Spotless

Code formatter that enforces consistent style.

### Minimal Configuration

```xml
<plugin>
    <groupId>com.diffplug.spotless</groupId>
    <artifactId>spotless-maven-plugin</artifactId>
    <version>2.43.0</version>
    <configuration>
        <java>
            <googleJavaFormat>
                <version>1.19.2</version>
                <style>AOSP</style>
            </googleJavaFormat>
            <removeUnusedImports/>
            <trimTrailingWhitespace/>
            <endWithNewline/>
        </java>
    </configuration>
    <executions>
        <execution>
            <goals>
                <goal>check</goal>
            </goals>
        </execution>
    </executions>
</plugin>
```

### Command

```bash
mvn spotless:check          # Check formatting
mvn spotless:apply          # Auto-format code
```

---

## Maven Surefire

Unit test runner.

### Minimal Configuration

```xml
<plugin>
    <groupId>org.apache.maven.plugins</groupId>
    <artifactId>maven-surefire-plugin</artifactId>
    <version>3.3.1</version>
    <configuration>
        <parallel>methods</parallel>
        <threadCount>4</threadCount>
        <includes>
            <include>**/*Test.java</include>
            <include>**/*Tests.java</include>
        </includes>
    </configuration>
</plugin>
```

---

## Maven Failsafe

Integration test runner.

### Minimal Configuration

```xml
<plugin>
    <groupId>org.apache.maven.plugins</groupId>
    <artifactId>maven-failsafe-plugin</artifactId>
    <version>3.3.1</version>
    <executions>
        <execution>
            <goals>
                <goal>integration-test</goal>
                <goal>verify</goal>
            </goals>
        </execution>
    </executions>
    <configuration>
        <includes>
            <include>**/*IT.java</include>
            <include>**/*IntegrationTest.java</include>
        </includes>
    </configuration>
</plugin>
```

---

## Complete pom.xml Plugin Management Snippet

```xml
<build>
    <pluginManagement>
        <plugins>
            <plugin>
                <groupId>com.github.spotbugs</groupId>
                <artifactId>spotbugs-maven-plugin</artifactId>
                <version>4.8.6.0</version>
            </plugin>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-pmd-plugin</artifactId>
                <version>3.23.0</version>
            </plugin>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-checkstyle-plugin</artifactId>
                <version>3.4.0</version>
            </plugin>
            <plugin>
                <groupId>org.jacoco</groupId>
                <artifactId>jacoco-maven-plugin</artifactId>
                <version>0.8.12</version>
            </plugin>
            <plugin>
                <groupId>org.owasp</groupId>
                <artifactId>dependency-check-maven</artifactId>
                <version>10.0.3</version>
            </plugin>
            <plugin>
                <groupId>com.diffplug.spotless</groupId>
                <artifactId>spotless-maven-plugin</artifactId>
                <version>2.43.0</version>
            </plugin>
        </plugins>
    </pluginManagement>
</build>
```

# Installation Guide for ETAP Platform

## System Requirements

### Operating System
- Windows 10/11, macOS 10.15+, or Linux (Ubuntu 20.04+, CentOS 8+)
- 64-bit architecture required
- Minimum 8GB RAM (16GB recommended)
- 10GB available disk space

### Python Environment
- **Python 3.8 or higher** (now compatible with Python 3.8+)
- pip package manager
- virtual environment support

### Additional Dependencies
- Git version control system
- C compiler for native extensions (GCC on Linux/macOS, MSVC on Windows)

## Prerequisites

### Python Installation
Ensure Python 3.8+ is installed on your system:

**Windows:**
1. Download Python from [python.org](https://www.python.org/downloads/)
2. During installation, check "Add Python to PATH"

**macOS:**
```bash
# Using Homebrew
brew install python@3.9

# Or using pyenv
brew install pyenv
pyenv install 3.9.16
pyenv global 3.9.16
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv
```

**Linux (CentOS/RHEL):**
```bash
sudo yum install python3 python3-pip
# Or for newer versions:
sudo dnf install python3 python3-pip
```

### Git Installation
**Windows/macOS:** Download from [git-scm.com](https://git-scm.com/)

**Linux:**
```bash
# Ubuntu/Debian
sudo apt install git

# CentOS/RHEL
sudo yum install git
# Or for newer versions:
sudo dnf install git
```

### Verify Prerequisites
```bash
# Check Python version
python --version
# Should show Python 3.8 or higher

# Check pip version
pip --version
# Should show pip version

# Check Git version
git --version
# Should show Git version
```

## Installation Steps

### 1. Clone the Repository

```bash
git clone https://github.com/ahmdelbaz28-ux/revit.git
cd revit
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python -m venv etap-env

# Activate on Windows
etap-env\Scripts\activate

# Activate on macOS/Linux
source etap-env/bin/activate
```

### 3. Upgrade pip

```bash
python -m pip install --upgrade pip
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

> **Note**: If you encounter compilation issues with certain packages (especially numpy, scipy), you may need to install Microsoft C++ Build Tools on Windows or Xcode Command Line Tools on macOS.

### 5. Install ETAP Package

```bash
# Install in development mode
pip install -e .
```

## Platform-Specific Instructions

### Windows Installation

1. **Install Python**:
   - Download from [python.org](https://www.python.org/downloads/)
   - During installation, check "Add Python to PATH"
   - Verify installation: `python --version`

2. **Open Command Prompt or PowerShell** as administrator (recommended)

3. **Create virtual environment**:
   ```cmd
   python -m venv etap-env
   etap-env\Scripts\activate
   ```

4. **Install ETAP**:
   ```cmd
   pip install --upgrade pip
   pip install etap
   ```

5. **Verify installation**:
   ```cmd
   etap --version
   ```

### macOS Installation

1. **Install Python** (if not already installed):
   ```bash
   # Using Homebrew (recommended)
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   brew install python@3.9
   ```

2. **Open Terminal**

3. **Create virtual environment**:
   ```bash
   python3 -m venv etap-env
   source etap-env/bin/activate
   ```

4. **Install ETAP**:
   ```bash
   pip install --upgrade pip
   pip install etap
   ```

5. **Verify installation**:
   ```bash
   etap --version
   ```

### Linux Installation

#### Ubuntu/Debian

1. **Update package list**:
   ```bash
   sudo apt update
   ```

2. **Install Python and pip**:
   ```bash
   sudo apt install python3 python3-pip python3-venv
   ```

3. **Create virtual environment**:
   ```bash
   python3 -m venv etap-env
   source etap-env/bin/activate
   ```

4. **Install ETAP**:
   ```bash
   pip install --upgrade pip
   pip install etap
   ```

5. **Verify installation**:
   ```bash
   etap --version
   ```

#### CentOS/RHEL/Fedora

1. **Install Python and pip**:
   ```bash
   # CentOS/RHEL
   sudo yum install python3 python3-pip
   # Or for newer versions:
   sudo dnf install python3 python3-pip
   ```

2. **Create virtual environment**:
   ```bash
   python3 -m venv etap-env
   source etap-env/bin/activate
   ```

3. **Install ETAP**:
   ```bash
   pip install --upgrade pip
   pip install etap
   ```

4. **Verify installation**:
   ```bash
   etap --version
   ```

## Docker Installation (Alternative)

For containerized deployment:

```bash
# Build Docker image
docker build -t etap .

# Run in container
docker run -it etap
```
   ```

## Development Setup

For development purposes:

```bash
# Install with development dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```
   ```

### Installing Specific Versions

1. **Install a specific version**:
   ```bash
   pip install etap==1.2.3
   ```

2. **Install pre-release version**:
   ```bash
   pip install --pre etap
   ```

3. **Install from a specific branch/tag**:
   ```bash
   pip install git+https://github.com/your-org/etap.git@branch-name
   ```

## Verification Steps

### 1. Check Python Version

```bash
python --version
```

Expected: Python 3.8 or higher

### 2. Test Basic Import

```bash
python -c "import etap; print('ETAP imported successfully')"
```

### 3. Run Basic Commands

```bash
# Check available CLI commands
python -m etap.cli --help

# Initialize a new project
python -m etap.cli init
```

## Post-Installation Configuration

### 1. Environment Variables

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env` with your specific configuration.

### 2. Database Initialization

```bash
# Initialize database
alembic upgrade head
```

### First-Time Setup

1. **Run first-time setup**:
   ```bash
   etap setup
   ```

2. **Create admin user** (if applicable):
   ```bash
   etap user create-admin --username admin --email admin@example.com
   ```

## Troubleshooting

### Common Issues

#### 1. Compilation Errors
If you encounter compilation errors during installation:

**Windows:**
- Install Microsoft C++ Build Tools
- Or use pre-compiled wheels: `pip install --only-binary=all -r requirements.txt`

**macOS:**
- Install Xcode Command Line Tools: `xcode-select --install`

**Linux:**
- Install build essentials: `sudo apt-get install build-essential`

#### 2. Memory Issues
For systems with limited RAM:
- Increase virtual memory/swapping
- Install packages individually: `pip install <package-name>`
- Use `--no-cache-dir` flag: `pip install --no-cache-dir <package>`

#### 3. Permission Issues
If you encounter permission errors:
- Use virtual environment (recommended)
- Use `--user` flag: `pip install --user -r requirements.txt`

### Environment Setup Verification

```bash
# Verify Python version
python --version

# Verify pip
pip --version

# Verify installed packages
pip list | grep etap
```

   ```

---

## Next Steps

After successful installation:

1. Review the [QUICKSTART.md](QUICKSTART.md) guide
2. Explore the [DEVELOPMENT.md](DEVELOPMENT.md) documentation
3. Check the [TROUBLESHOOTING.md](TROUBLESHOOTING.md) guide for advanced topics

## Support

If you encounter issues during installation:

- Check the [TROUBLESHOOTING.md](TROUBLESHOOTING.md) guide
- Search existing GitHub issues
- Create a new issue with detailed error information
- Include your operating system, Python version, and error messages

---

**Important**: Remember that ETAP is a safety-critical system. Ensure your installation environment meets security requirements before using in production scenarios.
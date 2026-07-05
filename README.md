# Record Level Lineage POC

A Python-based utility for tracing data lineage in Denodo. This tool connects to the Denodo metadata repository using JDBC (JayDeBeApi) to perform lineage diagnostics and extract upstream/downstream dependencies.

## Project Structure

The project follows a modular service-based architecture:

```text
record_level_lineage_poc/
+-- config/                 # Configuration management
¦   +-- settings.py         # Loads variables from .env
+-- database/               # Database connectivity layer
¦   +-- connection.py       # Handles JayDeBeApi connections
+-- services/               # Business logic
¦   +-- connection_test.py  # Diagnostic & validation logic
+-- main.py                 # Application entry point (Pre-flight checks)
+-- .env                    # Secrets (Excluded from Git)
+-- requirements.txt        # Python dependencies
```

## Prerequisites

Before running the application, ensure you have the following installed:

- Python 3.10+  
- Java (JDK/JRE 11 or 17) - Required for the JDBC driver.  
  Verify by running:

```bash
java -version
```

---

## Setup Instructions

### 1. Clone the Repository
```bash
git clone https://github.com/gsk-tech/Record-level-lineage.git
cd Record-level-lineage
```

### 2. Install Dependencies
It is recommended to use a virtual environment:

```bash
pip install -r requirements.txt
```

### 3. Add the JDBC Driver
Important: The Denodo JDBC driver is not included in this repository due to size and licensing.  

Locate the file: `denodo-vdp-jdbcdriver-9.3.5.jar`  
Place it in the **root folder** of this project (same level as `main.py`).

### 4. Configure Credentials (.env)
Create a file named `.env` in the root directory. This file is ignored by Git for security.  

Template:

```ini
# .env file configuration
DENODO_HOST=denodo-eus2-dev.gsk.com
DENODO_PORT=9999
DENODO_DB=ddfmetadata_dev
DENODO_USER=YOUR_USERNAME_HERE
DENODO_PASSWORD=YOUR_PASSWORD_HERE
JDBC_DRIVER_PATH=denodo-vdp-jdbcdriver-9.3.5.jar
```

---

## Usage

To run the application and perform connection diagnostics:

```bash
python main.py
```

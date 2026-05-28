# Auto Generate Proxy Bot

This is a Python bot that automatically collects free proxies from the internet, verifies them, and stores the working proxies in a file.

## Installation

### 1. Clone the Repository

First, clone this repository to your local machine:
```sh
git clone https://github.com/qdans/Auto-Generate-Proxy.git
cd Auto-Generate-Proxy
```

### 2. Create and Activate a Virtual Environment

It is recommended to use a virtual environment to manage dependencies. Follow these steps:

#### On Windows:
```sh
python -m venv venv
venv\Scripts\activate
```

#### On Linux/macOS:
```sh
python3 -m venv venv
source venv/bin/activate
```

After activating the virtual environment, you will see `(venv)` at the beginning of your terminal prompt.

### 3. Install Dependencies

Once the virtual environment is activated, install the required dependencies:
```sh
pip install -r requirements.txt
```

## Usage

Run the script using:
```sh
python main.py #or python3 main.py
```

The working proxies will be saved in `working_proxies.txt`.
To stop bot `Ctrl+C`.

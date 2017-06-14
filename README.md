# Convex
Bitcoin Trading System

# Setup
Git Clone:
- git clone <ssh path> <project name>

(Optional)
    - Set up virtualenv
        - pip install virtualenv
    - cd <project folder>
    - virtualenv -p /usr/bin/python3 venv
    - source venv/bin/activate [You should notice your terminal prompt prefix with this name]

- pip install -r requirements.txt
- export PYTHONPATH=. [Do this only in the project directory. This will look for any called files within the directory you are in]
- Try it out:
    - run ./examples/gdax_example.py

## Documentation
Documentation can be generated by running

```bash
$ cd docs/
$ make html
```

## Tests

Tests can be ran by running `py.test` in the top level module.

## Running The Application
We have a micro service basic architecture with GUI pieces.
The Dashboard is the main GUI right now.
    - To launch the dashboard:
        - ./services/dashboard.py
    - To launch the services that it needs:
        - ./services/depth_feed.py
        - ./services/click_trader.py <API_KEY> <API_SECRET> <PASSPHRASE> 0.0.0.0 8003

Limitations:
    - Most of the configuration for the GUI's are hard coded as of right now. Need to make this configurable in some intelligible way.

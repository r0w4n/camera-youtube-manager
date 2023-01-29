# Camera Youtube Scheduler
Provides the ability to schdule youtube live streams for IP camera.

## Assumptions
Each camera has it's own youtube account.

# Installation
```pip3 install -r requirements.txt```

# Requirements
## Settings
A settings file, settings.json is required in the format of:
```
{
    "cameras": [
        {
            "name": "cam1",
            "title": "title used to name the youtube live stream",
            "description": "description of the youtube live stream",
            "enabled": true
        }
    ]
}
```

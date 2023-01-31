# Camera Youtube Manager

Provides the ability to schedule youtube live streams and manage the streams for IP camera.

# Requirements

* Requires the creation of a [Google Cloud Project](https://console.cloud.google.com/).
* Runs on Linux like environment
* [Screen](https://www.gnu.org/software/screen/) is installed
* Each camera has it's own youtube account.

# Installation

`pip3 install -r requirements.txt`



## Settings

A settings file, settings.json saved in the root of the project, is required in the format of:

```
{
    "cameras": [
        {
            "name": "cam1",
            "title": "title used to name the youtube live stream",
            "description": "description of the youtube live stream",
            "enabled": true,
            "url": "user:password@192.168.1.1/ISAPI/Streaming/Channels/101/picture",
            "key": "sdfs-sdfd-sdfs-sdfs-sdfd"
        }
    ]
}
```

## Client Secret

A client_secret.json file is required and saved in the root of the project. This is a oauth clienti id and is obtained from [Google Cloud Project Credentials](https://console.cloud.google.com/apis/credentials)

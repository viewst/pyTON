# pyTON

Python API for libtonlibjson (Telegram Open Network Light Client).
This project is loosely based on [formony ton_client](https://github.com/formony/ton_client)

## Installation

This client works with Python 3.7 only.

Prerequisites: 
* [Pipfile](https://github.com/pypa/pipfile)

* pyTON is been shipped with prebuilt fullnode's client library for Ubuntu Xenial & latest macOS. 
In case of incompatibility with your distro it's needed to build TON fullnode's libtonlibjson.so / libtonlibjson.dylib depends on archtecture. 
Check [here](/docs/ton.md) for fullnode's build instructions.
Don't forget to copy library file to pyTON/distlib/linux/libtonlibjson.so or pyTON/distlib/darwin/libtonlibjson.dylib


### Install using pip
`pip3 install pyTON`

## Running as a webserver
`python3 -m pyTON`

Options: 
1. `--port` - default 8000 - webserver port
2. `--getmethods` - default False - allow runGetMethod endpoint. Note, that generally it is unsafe to allow arbitrary method executions since maliciously constructed getMethod may crash liteclient.

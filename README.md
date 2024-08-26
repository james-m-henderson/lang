# FreeCONF Language Support

Interface for binding other computer languages to the FreeCONF Go core

## Dependencies

- protoc
- python3
- golang > 1.20

## Build and test

```
make deps-go deps-py
make all
```

## Debugging

```bash
# Which binary to run for language support for FreeCONF's core engine
FC_LANG_EXEC=fc-lang

# Opens a port to listen for Go's Delve debugger on port 999
FC_LANG_DBG_ADDR=:9999
```

## Setting up protoc

Download protoc from https://github.com/protocolbuffers/protobuf/releases

```
sudo mkdir /opt/protoc
sudo unzip -d /opt/protoc/ ./protoc-21.12-linux-x86_64.zip
export PATH=$PATH:/opt/protoc/bin
go install google.golang.org/protobuf/cmd/protoc-gen-go@v1.28
go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@v1.2
```


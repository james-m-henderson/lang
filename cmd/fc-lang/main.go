package main

import (
	"log"
	"os"
	"runtime/trace"
	"flag"

	"github.com/freeconf/lang"
)

const usage = `Usage: %s [--trace] path-to-socket-file path-to-x-socket-file

path-to-socket-file - name of the domain socket file this executable will create
    that will host the gRPC server defined in fc.proto.

path-to-x-socket-file - name of the domain socket file that the program calling
    this executable has hosted the gRPC server defined in fc-x.proto.
`

func main() {
	// Define the --trace flag
	traceFlag := flag.Bool("trace", false, "Enable tracing and save output to trace.out")
	flag.Parse()

	// Check if the required arguments are provided
	if len(flag.Args()) < 2 {
		log.Fatalf(usage, os.Args[0])
	}

	// Start tracing if the --trace flag is set
	if *traceFlag {
		f, err := os.Create("trace.out")
		chkerr(err)
		defer f.Close()

		err = trace.Start(f)
		chkerr(err)
		defer trace.Stop()
	}

	// Initialize the Driver
	d, err := lang.NewDriver(flag.Args()[0], flag.Args()[1])
	chkerr(err)

	// Serve the gRPC server
	chkerr(d.Serve())
}

func chkerr(err error) {
	if err != nil {
		panic(err)
	}
}

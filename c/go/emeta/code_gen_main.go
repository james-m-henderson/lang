//go:build ignore
// +build ignore

// core_gen generates boilerplate functions for meta structs looking
// at specfic field names and generating functions based on that.

package main

import (
	"os"

	"github.com/freeconf/lang/c/go/emeta"
)

func main() {
	structs, err := emeta.ParseSource("./meta.go")
	chkerr(err)
	dest, err := os.Create("../../src/meta.h")
	chkerr(err)
	defer dest.Close()
	err = emeta.GenerateSource(structs, "./templates/meta.h.tmpl", dest)
	chkerr(err)
}

func chkerr(err error) {
	if err != nil {
		panic(err)
	}
}

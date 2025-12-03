package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"log"
	"os"
	"time"

	"chunker-service/pkg/chunking"
)

// cliConfig holds flag values for the chunker CLI.
type cliConfig struct {
	PlanJSON string
	MetaJSON string
}

func parseFlags() cliConfig {
	var cfg cliConfig
	flag.StringVar(&cfg.PlanJSON, "plan-json", "", "JSON-encoded ChunkingPlan")
	flag.StringVar(&cfg.MetaJSON, "meta-json", "{}", "JSON-encoded base metadata map")
	flag.Parse()
	return cfg
}

func main() {
	cfg := parseFlags()

	if cfg.PlanJSON == "" {
		log.Fatalf("missing required --plan-json argument")
	}

	plan := chunking.ChunkingPlan{}
	if err := json.Unmarshal([]byte(cfg.PlanJSON), &plan); err != nil {
		log.Fatalf("invalid plan-json: %v", err)
	}

	baseMeta := map[string]interface{}{}
	if err := json.Unmarshal([]byte(cfg.MetaJSON), &baseMeta); err != nil {
		log.Fatalf("invalid meta-json: %v", err)
	}

	input, err := io.ReadAll(os.Stdin)
	if err != nil {
		log.Fatalf("failed to read stdin: %v", err)
	}

	text := string(input)

	chunker := chunking.NewSlidingWindowChunker()
	chunks, err := chunker.Chunk(text, plan, baseMeta)
	if err != nil {
		// While the actual chunking is not implemented, make the error
		// explicit to callers.
		if err == chunking.ErrNotImplemented {
			log.Fatalf("chunker not implemented: %v", err)
		}
		log.Fatalf("chunker error: %v", err)
	}

	// Ensure all chunks have basic metadata fields populated where possible.
	for i := range chunks {
		if chunks[i].CreatedAt.IsZero() {
			chunks[i].CreatedAt = time.Now().UTC()
		}
	}

	enc := json.NewEncoder(os.Stdout)
	if err := enc.Encode(chunks); err != nil {
		log.Fatalf("failed to encode chunks: %v", err)
	}

	fmt.Fprintln(os.Stderr, "chunking completed")
}

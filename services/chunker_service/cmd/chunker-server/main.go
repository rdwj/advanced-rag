package main

import (
	"encoding/json"
	"log"
	"net/http"
	"time"

	"chunker-service/pkg/chunking"
)

type chunkRequest struct {
	Text string                 `json:"text"`
	Plan chunking.ChunkingPlan  `json:"plan"`
	Meta map[string]interface{} `json:"meta"`
}

type errorResponse struct {
	Error string `json:"error"`
}

func writeJSON(w http.ResponseWriter, status int, v interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func handleChunk(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeJSON(w, http.StatusMethodNotAllowed, errorResponse{Error: "use POST"})
		return
	}
	var req chunkRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, errorResponse{Error: "invalid JSON body"})
		return
	}
	if req.Plan.WindowSize <= 0 {
		writeJSON(w, http.StatusBadRequest, errorResponse{Error: "plan.window_size must be > 0"})
		return
	}
	chunker := chunking.NewSlidingWindowChunker()
	chunks, err := chunker.Chunk(req.Text, req.Plan, req.Meta)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, errorResponse{Error: err.Error()})
		return
	}
	now := time.Now().UTC()
	for i := range chunks {
		if chunks[i].CreatedAt.IsZero() {
			chunks[i].CreatedAt = now
		}
	}
	writeJSON(w, http.StatusOK, chunks)
}

func handleHealth(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("/chunk", handleChunk)
	mux.HandleFunc("/healthz", handleHealth)

	addr := ":8080"
	log.Printf("chunker service listening on %s", addr)
	if err := http.ListenAndServe(addr, mux); err != nil {
		log.Fatalf("server error: %v", err)
	}
}

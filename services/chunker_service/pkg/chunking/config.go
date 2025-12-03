package chunking

// Mode defines the unit type used for sliding window chunking.
// It is intentionally simple so this package has minimal dependencies
// and can be called from other languages or processes.
type Mode string

const (
	ModeCharacters Mode = "chars"
	ModeTokens     Mode = "tokens"
	ModeLines      Mode = "lines"
)

// ChunkingPlan describes how a piece of text should be chunked.
// The plan is produced by an LLM (or other heuristic) and then
// executed deterministically by the chunker implementation.
type ChunkingPlan struct {
	WindowSize       int    `json:"window_size"`
	Overlap          int    `json:"overlap"`
	Mode             Mode   `json:"mode"`
	BreakOnHeadings  bool   `json:"break_on_headings"`
	IncludeHeadings  bool   `json:"include_headings,omitempty"`
	MaxChunks        int    `json:"max_chunks,omitempty"`
	Notes            string `json:"notes,omitempty"`
}

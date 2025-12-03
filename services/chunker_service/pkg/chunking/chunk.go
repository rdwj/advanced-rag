package chunking

import "time"

// Chunk represents a single chunk of text along with useful metadata
// for retrieval and debugging. It is designed to be serializable as JSON.
type Chunk struct {
	ID         string                 `json:"id"`
	Text       string                 `json:"text"`
	StartIndex int                    `json:"start_index"`
	EndIndex   int                    `json:"end_index"`
	Page       *int                   `json:"page,omitempty"`
	Section    string                 `json:"section,omitempty"`
	FileName   string                 `json:"file_name"`
	FilePath   string                 `json:"file_path"`
	MimeType   string                 `json:"mime_type"`
	CreatedAt  time.Time              `json:"created_at"`
	Extra      map[string]interface{} `json:"extra,omitempty"`
}

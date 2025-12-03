package chunking

import (
	"strings"
	"testing"
)

func TestChunkCharactersSlidingWindow(t *testing.T) {
	chunker := NewSlidingWindowChunker()
	plan := ChunkingPlan{
		WindowSize: 2,
		Overlap:    1,
		Mode:       ModeCharacters,
	}
	meta := map[string]interface{}{
		"file_name": "example.txt",
		"file_path": "/tmp/example.txt",
		"mime_type": "text/plain",
		"doc_id":    42,
	}

	chunks, err := chunker.Chunk("abcd", plan, meta)
	if err != nil {
		t.Fatalf("chunking failed: %v", err)
	}

	if got, want := len(chunks), 3; got != want {
		t.Fatalf("expected %d chunks, got %d", want, got)
	}

	wantTexts := []string{"ab", "bc", "cd"}
	for i, ch := range chunks {
		if ch.Text != wantTexts[i] {
			t.Errorf("chunk %d text = %q, want %q", i, ch.Text, wantTexts[i])
		}
		if ch.StartIndex != i || ch.EndIndex != i+plan.WindowSize && i < len(chunks)-1 {
			t.Errorf("chunk %d indices = (%d,%d), want start %d", i, ch.StartIndex, ch.EndIndex, i)
		}
		if ch.FileName != meta["file_name"] {
			t.Errorf("file_name not propagated")
		}
		if ch.FilePath != meta["file_path"] {
			t.Errorf("file_path not propagated")
		}
		if ch.MimeType != meta["mime_type"] {
			t.Errorf("mime_type not propagated")
		}
		if ch.Extra["doc_id"] != meta["doc_id"] {
			t.Errorf("extra metadata missing doc_id")
		}
	}
}

func TestChunkTokens(t *testing.T) {
	chunker := NewSlidingWindowChunker()
	plan := ChunkingPlan{
		WindowSize: 3,
		Overlap:    1,
		Mode:       ModeTokens,
	}

	chunks, err := chunker.Chunk("a b c d e", plan, map[string]interface{}{})
	if err != nil {
		t.Fatalf("chunking failed: %v", err)
	}

	if got, want := len(chunks), 2; got != want {
		t.Fatalf("expected %d chunks, got %d", want, got)
	}
	if chunks[0].Text != "a b c" || chunks[1].Text != "c d e" {
		t.Fatalf("unexpected chunk texts: %+v", chunks)
	}
	if chunks[0].StartIndex != 0 || chunks[1].StartIndex != 2 {
		t.Fatalf("unexpected start indices: %d, %d", chunks[0].StartIndex, chunks[1].StartIndex)
	}
}

func TestChunkLines(t *testing.T) {
	chunker := NewSlidingWindowChunker()
	plan := ChunkingPlan{
		WindowSize: 2,
		Overlap:    0,
		Mode:       ModeLines,
	}

	chunks, err := chunker.Chunk("L1\nL2\nL3", plan, map[string]interface{}{})
	if err != nil {
		t.Fatalf("chunking failed: %v", err)
	}

	if got, want := len(chunks), 2; got != want {
		t.Fatalf("expected %d chunks, got %d", want, got)
	}
	if chunks[0].Text != "L1\nL2" {
		t.Errorf("first chunk text = %q, want L1\\nL2", chunks[0].Text)
	}
	if chunks[1].Text != "L3" {
		t.Errorf("second chunk text = %q, want L3", chunks[1].Text)
	}
}

func TestChunkMaxChunks(t *testing.T) {
	chunker := NewSlidingWindowChunker()
	plan := ChunkingPlan{
		WindowSize: 2,
		Overlap:    1,
		Mode:       ModeCharacters,
		MaxChunks:  2,
	}

	chunks, err := chunker.Chunk("abcde", plan, map[string]interface{}{})
	if err != nil {
		t.Fatalf("chunking failed: %v", err)
	}
	if got, want := len(chunks), 2; got != want {
		t.Fatalf("expected %d chunks after MaxChunks applied, got %d", want, got)
	}
}

func TestChunkEmptyInput(t *testing.T) {
	chunker := NewSlidingWindowChunker()
	plan := ChunkingPlan{
		WindowSize: 3,
		Overlap:    1,
		Mode:       ModeTokens,
	}

	chunks, err := chunker.Chunk("", plan, map[string]interface{}{})
	if err != nil {
		t.Fatalf("chunking failed: %v", err)
	}
	if len(chunks) != 0 {
		t.Fatalf("expected no chunks for empty input, got %d", len(chunks))
	}
}

func TestChunkValidationErrors(t *testing.T) {
	chunker := NewSlidingWindowChunker()

	_, err := chunker.Chunk("abc", ChunkingPlan{WindowSize: 0, Overlap: 0}, map[string]interface{}{})
	if err == nil {
		t.Fatalf("expected error for window_size <= 0")
	}

	_, err = chunker.Chunk("abc", ChunkingPlan{WindowSize: 2, Overlap: 2}, map[string]interface{}{})
	if err == nil {
		t.Fatalf("expected error for overlap >= window_size")
	}
}

func TestChunkBreakOnHeadings(t *testing.T) {
	chunker := NewSlidingWindowChunker()
	plan := ChunkingPlan{
		WindowSize:      3,
		Overlap:         1,
		Mode:            ModeLines,
		BreakOnHeadings: true,
	}

	text := "# INTRO\nalpha\nbeta\n2. Methods\nfoo\nbar"
	chunks, err := chunker.Chunk(text, plan, map[string]interface{}{})
	if err != nil {
		t.Fatalf("chunking failed: %v", err)
	}
	if len(chunks) == 0 {
		t.Fatalf("expected chunks with break_on_headings enabled")
	}
	for _, ch := range chunks {
		if strings.Contains(ch.Text, "beta") && strings.Contains(ch.Text, "2. Methods") {
			t.Fatalf("chunk should not cross heading boundary: %q", ch.Text)
		}
	}
	if chunks[0].StartIndex != 0 || !strings.HasPrefix(chunks[0].Text, "# INTRO") {
		t.Fatalf("first chunk should start at first heading, got %+v", chunks[0])
	}
}

func TestChunkIncludeHeadings(t *testing.T) {
	chunker := NewSlidingWindowChunker()
	plan := ChunkingPlan{
		WindowSize:      2,
		Overlap:         1,
		Mode:            ModeLines,
		BreakOnHeadings: true,
		IncludeHeadings: true,
	}

	text := "## Heading\nline1\nline2\nline3"
	chunks, err := chunker.Chunk(text, plan, map[string]interface{}{})
	if err != nil {
		t.Fatalf("chunking failed: %v", err)
	}
	if len(chunks) == 0 {
		t.Fatalf("expected chunks")
	}
	if !strings.HasPrefix(chunks[0].Text, "Heading\nline1") {
		t.Fatalf("expected heading to be prefixed in chunk text, got %q", chunks[0].Text)
	}
	if chunks[0].Extra["heading"] != "Heading" {
		t.Fatalf("expected heading metadata, got %+v", chunks[0].Extra)
	}
	if lvl, ok := chunks[0].Extra["heading_level"].(int); !ok || lvl != 2 {
		t.Fatalf("expected heading level 2, got %+v", chunks[0].Extra)
	}
}

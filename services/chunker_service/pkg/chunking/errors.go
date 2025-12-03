package chunking

import "errors"

// ErrNotImplemented is returned by placeholder functions where the
// underlying logic has not yet been implemented.
var ErrNotImplemented = errors.New("chunking not implemented")

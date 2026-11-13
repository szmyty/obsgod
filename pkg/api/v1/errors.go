package v1

import (
	"context"
	"errors"
	"fmt"

	"github.com/szmyty/obsgod/pkg/automation"
)

type ErrorCode string

const (
	InvalidInput     ErrorCode = "invalid_input"
	ApprovalRequired ErrorCode = "approval_required"
	Authentication   ErrorCode = "authentication"
	Unavailable      ErrorCode = "unavailable"
	Timeout          ErrorCode = "timeout"
	Cancelled        ErrorCode = "cancelled"
	Conflict         ErrorCode = "conflict"
	OBSRequest       ErrorCode = "obs_request"
	Internal         ErrorCode = "internal"
)

// Error exposes a fixed diagnostic and optional OBS status code. Server comments,
// input values, endpoint addresses and arbitrary underlying errors are excluded.
type Error struct {
	Code      ErrorCode `json:"code"`
	Operation string    `json:"operation"`
	OBSCode   int       `json:"obs_code,omitempty"`
	Retryable bool      `json:"retryable"`
	cause     error
}

func (e *Error) Error() string {
	return fmt.Sprintf("OBS API %s: %s; %s", e.Operation, e.Code, e.Remediation())
}
func (e *Error) Unwrap() error { return e.cause }
func (e *Error) Remediation() string {
	switch e.Code {
	case InvalidInput:
		return "validate the documented inputs and profile"
	case ApprovalRequired:
		return "supply explicit approval for this invocation"
	case Authentication:
		return "check the OBS WebSocket password through a private secret source"
	case Unavailable:
		return "start OBS and enable its built-in WebSocket server, then reconnect"
	case Timeout, Cancelled:
		return "inspect OBS state before retrying; an interrupted mutation may have applied"
	case Conflict:
		return "inspect active outputs and current OBS configuration before retrying"
	case OBSRequest:
		return "inspect OBS diagnostics and the numeric request status"
	default:
		return "inspect local diagnostics and reconnect before retrying"
	}
}

// ExitCode preserves the CLI's existing 0-success/1-failure contract. Error.Code
// provides the stable machine classification without breaking legacy scripts.
func ExitCode(err error) int {
	if err != nil {
		return 1
	}
	return 0
}

// Failure converts external errors without retaining free-form error strings.
func Failure(operation string, err error) *Error {
	if err == nil {
		return nil
	}
	e := &Error{Operation: safeOperation(operation), Code: Internal}
	var known *Error
	if errors.As(err, &known) {
		e.Code, e.OBSCode, e.Retryable, e.cause = known.Code, known.OBSCode, known.Retryable, known.cause
		return e
	}
	switch {
	case errors.Is(err, automation.ErrServiceMismatch):
		e.Code = Conflict
	case errors.Is(err, context.Canceled):
		e.Code, e.cause = Cancelled, context.Canceled
	case errors.Is(err, context.DeadlineExceeded):
		e.Code, e.cause = Timeout, context.DeadlineExceeded
	default:
		var connection *automation.ConnectionError
		var request *automation.RequestError
		if errors.As(err, &connection) {
			switch connection.Kind {
			case "authentication":
				e.Code = Authentication
			case "timeout":
				e.Code, e.Retryable = Timeout, true
			default:
				e.Code, e.Retryable = Unavailable, true
			}
		} else if errors.As(err, &request) {
			e.Code, e.OBSCode = OBSRequest, request.Code
		}
	}
	return e
}
func fail(operation string, code ErrorCode) *Error {
	return &Error{Operation: safeOperation(operation), Code: code}
}
func safeOperation(operation string) string {
	for _, item := range Discover().Operations {
		if operation == item {
			return operation
		}
	}
	switch operation {
	case "connect", "close", "creator.start", "creator.stop", "creator.status", "creator.plan", "workflow.validate":
		return operation
	}
	return "request"
}

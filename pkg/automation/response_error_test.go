package automation

import (
	"context"
	"errors"
	"fmt"
	"net"
	"strings"
	"testing"
)

func TestResponseFailureClassificationExcludesServerDetails(t *testing.T) {
	const secret = "private-endpoint/password/key"
	for _, tc := range []struct {
		name        string
		err         error
		timeout     bool
		response    bool
		requestCode int
	}{
		{name: "sdk timeout", err: errors.New("request StartStream: timeout waiting for response from server"), timeout: true, response: true},
		{name: "wrong response ID", err: errors.New("request StartStream: mismatched ID: expected response with ID generated, but got " + secret + " (600)"), response: true},
		{name: "disconnected", err: errors.New("request StartStream: client already disconnected"), response: true},
		{name: "typed timeout", err: &net.DNSError{Err: secret, IsTimeout: true}, timeout: true, response: true},
		{name: "numeric rejection", err: errors.New("request StartStream: InvalidResourceState (604): " + secret + " timeout waiting for response from server (777)"), requestCode: 604},
		{name: "unknown numeric rejection", err: errors.New("request StartStream: EvenMoreUnknown (999): " + secret), requestCode: 999},
		{name: "untrusted parentheses", err: errors.New(secret + " (600)")},
		{name: "decode body resembling status", err: errors.New("request StartStream: decoding `InvalidResourceState (604): " + secret + "` into response")},
	} {
		t.Run(tc.name, func(t *testing.T) {
			err := requestFailure("StartStream", tc.err)
			var response *ResponseError
			if errors.As(err, &response) != tc.response || errors.Is(err, context.DeadlineExceeded) != tc.timeout {
				t.Fatalf("wrong response classification: %T %v", err, err)
			}
			if !tc.response {
				var request *RequestError
				if !errors.As(err, &request) || request.Code != tc.requestCode {
					t.Fatalf("wrong request classification: %T %v", err, err)
				}
			}
			if strings.Contains(fmt.Sprintf("%v %+v %#v", err, err, err), secret) {
				t.Fatal("raw response detail retained")
			}
		})
	}
}

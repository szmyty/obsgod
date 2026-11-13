package obs

import (
	"errors"
	"strings"
	"testing"

	"github.com/andreykaipov/goobs"
	"github.com/szmyty/obsgod/internal/config"
	api "github.com/szmyty/obsgod/pkg/api/v1"
)

func TestLegacyConnectionFailureRetainsContextWithoutRawSecrets(t *testing.T) {
	s := NewServiceWithDialer(&config.Config{Host: "127.0.0.1", Port: 4455, Password: "private-password"}, "test", func(string, ...goobs.Option) (*goobs.Client, error) {
		return nil, errors.New("server echoed private-password")
	})
	err := s.StartStream()
	if err == nil || strings.Contains(err.Error(), "private-password") || !strings.Contains(err.Error(), "connect to OBS at 127.0.0.1:4455") {
		t.Fatalf("legacy failure: %v", err)
	}
	var domain *api.Error
	if !errors.As(err, &domain) || domain.Code != api.Unavailable {
		t.Fatalf("missing shared domain error: %v", err)
	}
}
func TestLegacyRequestFailureDoesNotExposeComments(t *testing.T) {
	err := legacyError(errors.New("request failed (600): private-stream-key"))
	if err == nil || strings.Contains(err.Error(), "private-stream-key") {
		t.Fatal("request comment escaped")
	}
	if legacyError(nil) != nil {
		t.Fatal("nil error changed")
	}
}

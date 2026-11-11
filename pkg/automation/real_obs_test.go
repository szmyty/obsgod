package automation

import (
	"context"
	"os"
	"testing"
	"time"
)

// Explicit opt-in only. This reads version/status, never changes a live OBS.
func TestRealOBSReadOnly(t *testing.T) {
	address := os.Getenv("OBSGOD_TEST_OBS_ADDRESS")
	if address == "" {
		t.Skip("set OBSGOD_TEST_OBS_ADDRESS for opt-in real OBS reads")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	c, e := Connect(ctx, Config{Address: address, Password: os.Getenv("OBSGOD_TEST_OBS_PASSWORD"), Timeout: 3 * time.Second})
	if e != nil {
		t.Fatal(e)
	}
	defer c.Close()
	_, e = c.obs.General.GetVersion()
	if e != nil {
		t.Fatalf("GetVersion adapter returned %T", e)
	}
	r, e := c.RuntimeStatus(ctx)
	if e != nil {
		t.Fatal(e)
	}
	if r.Version == "" {
		t.Fatal("missing real OBS version")
	}
	t.Logf("OBS %s; managed profile=%s", r.Version, r.Profile)
}

package config

import (
	"encoding/json"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

func isolateEnvironment(t *testing.T) string {
	t.Helper()
	for _, key := range []string{"OBS_HOST", "OBS_PORT", "OBS_PASSWORD", "OBS_PASSWORD_FILE", "OBSGOD_HOST", "OBSGOD_PORT", "OBSGOD_PASSWORD", "OBSGOD_PASSWORD_FILE", "OBSGOD_CONFIG", "OBSGOD_CONNECTION_PROFILE"} {
		t.Setenv(key, "")
		// Empty passwords intentionally override a configured reference, so remove
		// these two bindings while leaving cleanup to testing's environment guard.
		if key == "OBS_PASSWORD" || key == "OBSGOD_PASSWORD" {
			if err := os.Unsetenv(key); err != nil {
				t.Fatal(err)
			}
		}
	}
	root := t.TempDir()
	t.Setenv("XDG_CONFIG_HOME", root)
	return root
}

func writeConfig(t *testing.T, root, document string) string {
	t.Helper()
	path := filepath.Join(root, "obsgod", "config.json")
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(document), 0o600); err != nil {
		t.Fatal(err)
	}
	return path
}

func TestConfigurationLayersAndConnectionProfiles(t *testing.T) {
	root := isolateEnvironment(t)
	path := writeConfig(t, root, `{"version":1,"connection":{"host":"file.example","port":4456},"default_profile":"studio","profiles":{"studio":{"host":"profile.example"},"deck":{"port":4457}}}`)
	base := Config{Host: "localhost", Port: 4455}
	resolved, err := Resolve(base, Options{Path: path})
	if err != nil {
		t.Fatal(err)
	}
	if resolved.Config.Host != "profile.example" || resolved.Config.Port != 4456 || resolved.Profile != "studio" || strings.Join(resolved.Profiles, ",") != "deck,studio" {
		t.Fatalf("file/profile layer incorrect: %+v", resolved.Public())
	}
	t.Setenv("OBS_HOST", "legacy.example")
	t.Setenv("OBS_PORT", "4458")
	resolved, err = Resolve(base, Options{Path: path, Profile: "deck"})
	if err != nil || resolved.Config.Host != "legacy.example" || resolved.Config.Port != 4458 {
		t.Fatalf("legacy environment should override selected file profile: %+v %v", resolved.Public(), err)
	}
	t.Setenv("OBSGOD_HOST", "canonical.example")
	t.Setenv("OBSGOD_PORT", "4459")
	resolved, err = Resolve(base, Options{Path: path})
	if err != nil || resolved.Config.Host != "canonical.example" || resolved.Config.Port != 4459 {
		t.Fatalf("canonical environment should override aliases: %+v %v", resolved.Public(), err)
	}
	flagHost, flagPort := "flag.example", uint32(4460)
	t.Setenv("OBSGOD_PORT", "bad-value-is-not-an-effective-port")
	resolved, err = Resolve(base, Options{Path: path, Host: &flagHost, Port: &flagPort})
	if err != nil || resolved.Config.Host != flagHost || resolved.Config.Port != flagPort {
		t.Fatalf("explicit flags should override environment, even malformed lower port: %+v %v", resolved.Public(), err)
	}
}

func TestOptionalDefaultAndExplicitMissingConfig(t *testing.T) {
	root := isolateEnvironment(t)
	base := Config{Host: "localhost", Port: 4455}
	resolved, err := Resolve(base, Options{})
	if err != nil || resolved.Loaded || resolved.Config != base {
		t.Fatalf("missing default must retain existing defaults: %+v %v", resolved.Public(), err)
	}
	_, err = Resolve(base, Options{Path: filepath.Join(root, "absent.json")})
	if err == nil {
		t.Fatal("explicit missing configuration must fail")
	}
	t.Setenv("OBSGOD_CONFIG", filepath.Join(root, "absent.json"))
	if _, err := Resolve(base, Options{}); err == nil {
		t.Fatal("explicit environment config must not silently disappear")
	}
}

func TestConfigErrorsNeverEchoCredentialMaterial(t *testing.T) {
	for _, body := range []string{
		`{"version":1,"password":"private-credential-marker"}`,
		`{"version":1,"connection":{"private-credential-marker":true}}`,
		`{"version":1,"connection":{"port":"private-credential-marker"}}`,
		`{"version":1} private-credential-marker`,
		`{"version":99}`,
		`{"version":1,"connection":{"password_env":"BAD-NAME"}}`,
		`{"version":1,"connection":{"password_env":"TOKEN","password_file":"private-credential-marker"}}`,
	} {
		t.Run(body, func(t *testing.T) {
			root := isolateEnvironment(t)
			path := writeConfig(t, root, body)
			_, err := Resolve(Config{Host: "localhost", Port: 4455}, Options{Path: path})
			if err == nil || strings.Contains(err.Error(), "private-credential-marker") {
				t.Fatalf("expected contextual redacted error, got %v", err)
			}
		})
	}
}

func TestPrivateSecretReferenceAndFlagPrecedence(t *testing.T) {
	root := isolateEnvironment(t)
	path := writeConfig(t, root, `{"version":1,"connection":{"password_file":"obs-password"}}`)
	secretPath := filepath.Join(filepath.Dir(path), "obs-password")
	if err := os.WriteFile(secretPath, []byte("private-credential-marker\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	base := Config{Host: "localhost", Port: 4455}
	resolved, err := Resolve(base, Options{Path: path})
	if err != nil || resolved.Config.Password != "private-credential-marker" || resolved.PasswordSource != "private_file" {
		t.Fatalf("relative secret-file reference failed: %v", err)
	}
	for _, value := range []any{resolved.Config, resolved.Public(), resolved} {
		encoded, err := json.Marshal(value)
		if err != nil || strings.Contains(string(encoded), "private-credential-marker") {
			t.Fatal("diagnostic JSON leaked credentials")
		}
	}
	t.Setenv("OBS_PASSWORD", "environment-marker")
	resolved, err = Resolve(base, Options{Path: path})
	if err != nil || resolved.Config.Password != "environment-marker" {
		t.Fatal("environment must override file reference")
	}
	resolved, err = Resolve(base, Options{Path: path, PasswordFile: secretPath})
	if err != nil || resolved.Config.Password != "private-credential-marker" {
		t.Fatal("explicit password file must override environment")
	}
	flagPassword := ""
	resolved, err = Resolve(base, Options{Path: path, Password: &flagPassword})
	if err != nil || resolved.Config.Password != "" || resolved.PasswordSource != "flag" {
		t.Fatal("explicit empty password flag must override lower layers")
	}
}

func TestSecretEnvironmentReferenceIsNotExpandedIntoDiagnostics(t *testing.T) {
	root := isolateEnvironment(t)
	path := writeConfig(t, root, `{"version":1,"connection":{"password_env":"TEST_OBSGOD_SECRET"}}`)
	t.Setenv("TEST_OBSGOD_SECRET", "private-credential-marker")
	resolved, err := Resolve(Config{Host: "localhost", Port: 4455}, Options{Path: path})
	if err != nil || resolved.Config.Password != "private-credential-marker" {
		t.Fatal("environment reference did not resolve")
	}
	encoded, _ := json.Marshal(resolved.Public())
	if strings.Contains(string(encoded), "private-credential-marker") || strings.Contains(string(encoded), "TEST_OBSGOD_SECRET") {
		t.Fatal("public diagnostics should show only a generic secret source")
	}
	if err := os.Unsetenv("TEST_OBSGOD_SECRET"); err != nil {
		t.Fatal(err)
	}
	if _, err := Resolve(Config{Host: "localhost", Port: 4455}, Options{Path: path}); err == nil {
		t.Fatal("missing referenced secret must fail with remediation")
	}
}

func TestSecretAndConfigFilesRejectUnsafeInputs(t *testing.T) {
	root := isolateEnvironment(t)
	secret := filepath.Join(root, "password")
	if err := os.WriteFile(secret, []byte("private-credential-marker"), 0o600); err != nil {
		t.Fatal(err)
	}
	if runtime.GOOS != "windows" {
		if err := os.Chmod(secret, 0o644); err != nil {
			t.Fatal(err)
		}
		if _, _, err := passwordFile(secret); err == nil {
			t.Fatal("group/world-readable secret accepted")
		}
		if err := os.Chmod(secret, 0o600); err != nil {
			t.Fatal(err)
		}
		link := filepath.Join(root, "link")
		if err := os.Symlink(secret, link); err != nil {
			t.Fatal(err)
		}
		if _, _, err := passwordFile(link); err == nil {
			t.Fatal("symlink secret accepted")
		}
		if _, _, err := loadFile(link, true); err == nil {
			t.Fatal("symlink configuration accepted")
		}
		configPath := writeConfig(t, root, `{"version":1}`)
		if err := os.Chmod(configPath, 0o666); err != nil {
			t.Fatal(err)
		}
		if _, _, err := loadFile(configPath, true); err == nil {
			t.Fatal("configuration writable by other users could redirect credential use")
		}
	}
	if err := os.WriteFile(secret, []byte(strings.Repeat("x", 16385)), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, _, err := passwordFile(secret); err == nil {
		t.Fatal("oversized secret accepted")
	}
	if err := os.WriteFile(secret, []byte("line-one\nline-two"), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, _, err := passwordFile(secret); err == nil {
		t.Fatal("multiline secret accepted")
	}
}

func TestProfileListingCanRecoverBadSelectionAndUnavailableSecrets(t *testing.T) {
	root := isolateEnvironment(t)
	path := writeConfig(t, root, `{"version":1,"default_profile":"missing","connection":{"password_file":"not-created"},"profiles":{"z":{"host":"z.example"},"a":{"host":"a.example"}}}`)
	names, err := ProfileNames(path)
	if err != nil || strings.Join(names, ",") != "a,z" {
		t.Fatalf("profile names must be usable without selected profile or its password: %v %v", names, err)
	}
	if _, err := Resolve(Config{Host: "localhost", Port: 4455}, Options{Path: path}); err == nil {
		t.Fatal("invalid selected profile must fail an operation")
	}
}

func TestInvalidAddressFailsWithoutEcho(t *testing.T) {
	isolateEnvironment(t)
	for _, cfg := range []Config{{Host: "user:private-credential-marker@example", Port: 4455}, {Host: "localhost", Port: 0}, {Host: "localhost", Port: 65536}, {Host: "::1", Port: 4455}, {Host: "localhost\nprivate-credential-marker", Port: 4455}} {
		_, err := Resolve(cfg, Options{})
		if err == nil || strings.Contains(err.Error(), "private-credential-marker") {
			t.Fatalf("invalid address should yield a redacted actionable error: %v", err)
		}
	}
	if _, err := Resolve(Config{Host: "[::1]", Port: 4455}, Options{}); err != nil {
		t.Fatalf("bracketed IPv6 should remain usable: %v", err)
	}
}

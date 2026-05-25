from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_backend_container_can_bind_to_tailscale_host_ip():
    compose = read_text("server/docker-compose.yml")

    assert '"${BACKEND_HOST_IP:-127.0.0.1}:8000:8000"' in compose
    assert "BACKEND_HOST_IP" in compose
    assert '"8000:8000"' not in compose


def test_postgres_container_is_not_publicly_bound():
    compose = read_text("server/docker-compose.yml")

    assert '"127.0.0.1:5433:5432"' in compose
    assert '"5433:5432"' not in compose


def test_tunnel_script_uses_tailscale_funnel_without_legacy_public_headers():
    script = read_text("scripts/start_backend_tunnel.ps1").lower()

    assert "tailscale" in script
    assert "funnel" in script
    assert "funnel status" in script
    assert "--yes" in script
    assert "ngrok" not in script


def test_tunnel_script_handles_disabled_funnel_without_hanging():
    script = read_text("scripts/start_backend_tunnel.ps1")

    assert "Start-Process" in script
    assert "Funnel is not enabled" in script
    assert "login\\.tailscale\\.com/f/funnel" in script
    assert "--terminate-on" not in script


def test_tunnel_script_writes_client_backend_config():
    script = read_text("scripts/start_backend_tunnel.ps1")

    assert "Write-ClientBackendConfig" in script
    assert "backend_url.txt" in script
    assert '"http://localhost:$Port"' in script


def test_client_build_script_autodetects_tailscale_funnel_url():
    script = read_text("scripts/build_client_installer.ps1")

    assert "Get-RunningTailscaleFunnelUrl" in script
    assert "Get-TailscaleBackendUrl" in script
    assert "tailscale funnel status" in script
    assert "Get-RunningNgrokUrl" not in script


def test_tailnet_start_script_writes_client_backend_config():
    script = read_text("scripts/start_backend_tailnet.ps1")

    assert "Get-TailscaleIp" in script
    assert "BACKEND_HOST_IP" in script
    assert "backend_url.txt" in script
    assert "docker compose" in script


def test_public_start_script_uses_cloudflare_quick_tunnel():
    script = read_text("scripts/start_backend_public.ps1")

    assert "cloudflared" in script.lower()
    assert "trycloudflare.com" in script
    assert "BACKEND_HOST_IP" in script
    assert "127.0.0.1" in script
    assert "build_client_installer.ps1" in script


def test_demo_dataset_script_creates_bounded_old_file_set():
    script = read_text("scripts/create_demo_dataset.ps1")

    assert "FileCount" in script
    assert "300" in script
    assert "SetLastWriteTime" in script
    assert "SetCreationTime" in script
    assert "DistinctExtensions" in script
    assert "old-driver-installer" in script
    assert "demo-scan-folder-300" in script

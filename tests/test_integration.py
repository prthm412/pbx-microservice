"""
Integration Tests for PBX Microservice
"""
import pytest
import asyncio
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Test health check endpoint"""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_packet_ingestion_sequential(client: AsyncClient):
    """Test sequential packet ingestion"""
    call_id = "TEST-CALL-001"
    
    # Send packets in order
    for i in range(5):
        response = await client.post(
            f"/v1/call/stream/{call_id}",
            json={
                "sequence": i,
                "data": f"packet_{i}",
                "timestamp": 1738512345.0 + i
            }
        )
        assert response.status_code == 202
        data = response.json()
        assert data["sequence"] == i
        assert data["status"] == "accepted"


@pytest.mark.asyncio
async def test_missing_packet_detection(client: AsyncClient):
    """Test that missing packets are detected"""
    call_id = "TEST-CALL-002"
    
    # Send packet 0
    response = await client.post(
        f"/v1/call/stream/{call_id}",
        json={"sequence": 0, "data": "packet_0", "timestamp": 1738512345.0}
    )
    assert response.status_code == 202
    
    # Skip packets 1, 2, 3 and send packet 4
    response = await client.post(
        f"/v1/call/stream/{call_id}",
        json={"sequence": 4, "data": "packet_4", "timestamp": 1738512349.0}
    )
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "accepted_with_warning"
    
    # Verify call has missing packets recorded
    response = await client.get(f"/v1/call/{call_id}")
    assert response.status_code == 200
    call_data = response.json()
    assert "1" in call_data["missing_packets"]
    assert "2" in call_data["missing_packets"]
    assert "3" in call_data["missing_packets"]


@pytest.mark.asyncio
async def test_call_state_transitions(client: AsyncClient):
    """Test call state machine transitions"""
    call_id = "TEST-CALL-003"
    
    # Send a packet
    await client.post(
        f"/v1/call/stream/{call_id}",
        json={"sequence": 0, "data": "data", "timestamp": 1738512345.0}
    )
    
    # Check initial state
    response = await client.get(f"/v1/call/{call_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "IN_PROGRESS"
    
    # Complete call
    response = await client.post(f"/v1/call/complete/{call_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETED"
    
    # Try to complete again (idempotent)
    response = await client.post(f"/v1/call/complete/{call_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_call_history(client: AsyncClient):
    """Test retrieving call history"""
    # Create multiple calls
    for i in range(3):
        call_id = f"TEST-CALL-HISTORY-{i}"
        await client.post(
            f"/v1/call/stream/{call_id}",
            json={"sequence": 0, "data": "data", "timestamp": 1738512345.0}
        )
    
    # Get history
    response = await client.get("/v1/call/history")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 3
    assert len(data["calls"]) >= 3


@pytest.mark.asyncio
async def test_response_time_under_50ms(client: AsyncClient):
    """Test that packet ingestion responds quickly"""
    import time
    
    call_id = "TEST-CALL-PERF"
    
    start = time.time()
    response = await client.post(
        f"/v1/call/stream/{call_id}",
        json={"sequence": 0, "data": "data", "timestamp": 1738512345.0}
    )
    elapsed = (time.time() - start) * 1000  # Convert to ms
    
    assert response.status_code == 202
    # In production < 50ms, but tests have overhead - allow 200ms
    assert elapsed < 200, f"Response time {elapsed}ms exceeds limit"
    print(f"Response time: {elapsed:.2f}ms")
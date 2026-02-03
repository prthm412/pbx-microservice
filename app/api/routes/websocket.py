"""
WebSocket Routes for Real-time Updates
"""
from typing import List, Dict
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from datetime import datetime
import json

from app.utils.logger import setup_logger

logger = setup_logger(__name__)

router = APIRouter()


class ConnectionManager:
    """
    Manages WebSocket connections for real-time updates
    """
    
    def __init__(self):
        # Store active connections: {client_id: WebSocket}
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str):
        """
        Accept new WebSocket connection
        
        Args:
            websocket: WebSocket connection
            client_id: Unique client identifier
        """
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"🔌 WebSocket client {client_id} connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, client_id: str):
        """
        Remove WebSocket connection
        
        Args:
            client_id: Client identifier to disconnect
        """
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"🔌 WebSocket client {client_id} disconnected. Total connections: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: dict, client_id: str):
        """
        Send message to specific client
        
        Args:
            message: Message dictionary
            client_id: Target client identifier
        """
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            await websocket.send_json(message)
    
    async def broadcast(self, message: dict):
        """
        Broadcast message to all connected clients
        
        Args:
            message: Message dictionary to broadcast
        """
        logger.info(f"📢 Broadcasting to {len(self.active_connections)} clients: {message.get('type')}")
        
        # Send to all active connections
        disconnected_clients = []
        
        for client_id, websocket in self.active_connections.items():
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to client {client_id}: {str(e)}")
                disconnected_clients.append(client_id)
        
        # Clean up disconnected clients
        for client_id in disconnected_clients:
            self.disconnect(client_id)
    
    async def broadcast_call_update(self, call_id: str, status: str, data: dict = None):
        """
        Broadcast call status update
        
        Args:
            call_id: Call identifier
            status: New call status
            data: Optional additional data
        """
        message = {
            "type": "call_update",
            "call_id": call_id,
            "status": status,
            "data": data or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.broadcast(message)
    
    async def broadcast_ai_result(self, call_id: str, transcription: str, sentiment: str):
        """
        Broadcast AI processing result
        
        Args:
            call_id: Call identifier
            transcription: AI transcription text
            sentiment: Sentiment analysis result
        """
        message = {
            "type": "ai_result",
            "call_id": call_id,
            "transcription": transcription,
            "sentiment": sentiment,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.broadcast(message)
    
    def get_connection_count(self) -> int:
        """Get number of active connections"""
        return len(self.active_connections)


# Global connection manager instance
manager = ConnectionManager()


@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """
    WebSocket endpoint for real-time updates
    
    Clients connect to: ws://localhost:8000/ws/{client_id}
    
    Message types sent to clients:
    - call_update: When call status changes
    - ai_result: When AI processing completes
    - packet_received: When new packet arrives
    
    Args:
        websocket: WebSocket connection
        client_id: Unique client identifier
    """
    await manager.connect(websocket, client_id)
    
    try:
        # Send welcome message
        await websocket.send_json({
            "type": "connected",
            "message": f"Welcome client {client_id}",
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Keep connection alive and listen for messages
        while True:
            # Receive messages from client (heartbeat, etc.)
            data = await websocket.receive_text()
            
            # Echo back for heartbeat
            await websocket.send_json({
                "type": "pong",
                "received": data,
                "timestamp": datetime.utcnow().isoformat()
            })
            
    except WebSocketDisconnect:
        manager.disconnect(client_id)
        logger.info(f"Client {client_id} disconnected normally")
    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {str(e)}")
        manager.disconnect(client_id)


@router.get("/ws/stats")
async def websocket_stats():
    """Get WebSocket connection statistics"""
    return {
        "active_connections": manager.get_connection_count(),
        "timestamp": datetime.utcnow().isoformat()
    }
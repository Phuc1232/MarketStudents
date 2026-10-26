from fastapi import WebSocket
from typing import Dict, List, Optional
import logging

logger = logging.getLogger("WebSocketChat")


class ConnectionManager:
    """Quản lý kết nối WebSocket: Kênh Chat (theo room) và Kênh Thông báo (theo user)."""

    def __init__(self):
        # Kênh Chat: conversation_id -> danh sách WebSocket
        self.active_rooms: Dict[int, List[WebSocket]] = {}
        # Kênh Chat: conversation_id -> {websocket: user_id}
        self.socket_users: Dict[int, Dict[WebSocket, int]] = {}
        # Kênh Thông báo: user_id -> danh sách WebSocket
        self.user_notification_sockets: Dict[int, List[WebSocket]] = {}
    # --------------------------------------------------------------------------
    # KÊNH CHAT (ROOM-BASED)
    # --------------------------------------------------------------------------

    async def connect(self, conversation_id: int, websocket: WebSocket, user_id: int) -> None:
        """Chấp thuận kết nối và thêm vào phòng chat."""
        await websocket.accept()
        if conversation_id not in self.active_rooms:
            self.active_rooms[conversation_id] = []
            self.socket_users[conversation_id] = {}

        self.active_rooms[conversation_id].append(websocket)
        self.socket_users[conversation_id][websocket] = user_id

        logger.info(f"[WS CHAT CONNECT] User #{user_id} vào phòng #{conversation_id}.")

    def disconnect(self, conversation_id: int, websocket: WebSocket, user_id: Optional[int] = None) -> None:
        """Xóa socket khỏi phòng chat và giải phóng bộ nhớ khi phòng rỗng."""
        if conversation_id in self.active_rooms:
            if websocket in self.active_rooms[conversation_id]:
                self.active_rooms[conversation_id].remove(websocket)

            if conversation_id in self.socket_users and websocket in self.socket_users[conversation_id]:
                del self.socket_users[conversation_id][websocket]

            # Xóa phòng rỗng để tránh rò rỉ RAM
            if not self.active_rooms[conversation_id]:
                del self.active_rooms[conversation_id]
                if conversation_id in self.socket_users:
                    del self.socket_users[conversation_id]
                logger.info(f"[WS ROOM CLOSED] Đã dọn dẹp phòng #{conversation_id}.")
            else:
                logger.info(f"[WS CHAT DISCONNECT] User #{user_id} rời phòng #{conversation_id}.")

    async def broadcast_to_room(self, conversation_id: int, message: dict) -> None:
        """Phát tán tin nhắn đến tất cả socket trong cùng phòng chat."""
        if conversation_id not in self.active_rooms:
            return

        dead_sockets: List[WebSocket] = []
        for socket in list(self.active_rooms[conversation_id]):
            try:
                await socket.send_json(message)
            except Exception as e:
                logger.warning(f"[WS BROADCAST ERROR] Lỗi gửi socket phòng #{conversation_id}: {str(e)}")
                dead_sockets.append(socket)

        # Dọn dẹp socket hỏng
        for dead in dead_sockets:
            uid = self.socket_users.get(conversation_id, {}).get(dead)
            self.disconnect(conversation_id, dead, uid)

    def is_user_in_room(self, conversation_id: int, user_id: int) -> bool:
        """Kiểm tra xem user_id có đang mở phòng chat này không."""
        if conversation_id not in self.socket_users:
            return False
        return user_id in self.socket_users[conversation_id].values()

    # --------------------------------------------------------------------------
    # KÊNH THÔNG BÁO TOÀN CỤC (USER-BASED)
    # --------------------------------------------------------------------------

    async def connect_user_notifications(self, websocket: WebSocket, user_id: int) -> None:
        """Chấp thuận kết nối kênh thông báo toàn cục của user."""
        await websocket.accept()
        if user_id not in self.user_notification_sockets:
            self.user_notification_sockets[user_id] = []

        self.user_notification_sockets[user_id].append(websocket)
        logger.info(f"[WS NOTIFICATION CONNECT] User #{user_id} kết nối kênh thông báo.")

    def disconnect_user_notifications(self, websocket: WebSocket, user_id: int) -> None:
        """Dọn dẹp socket thông báo khi user đóng tab/ngắt kết nối."""
        if user_id in self.user_notification_sockets:
            if websocket in self.user_notification_sockets[user_id]:
                self.user_notification_sockets[user_id].remove(websocket)

            if not self.user_notification_sockets[user_id]:
                del self.user_notification_sockets[user_id]
                logger.info(f"[WS NOTIFICATION OFFLINE] User #{user_id} đã offline kênh thông báo.")

    async def send_to_user(self, user_id: int, message: dict) -> bool:
        """Đẩy dữ liệu Real-time tới kênh thông báo của user cụ thể."""
        if user_id not in self.user_notification_sockets or not self.user_notification_sockets[user_id]:
            return False

        dead_sockets: List[WebSocket] = []
        sent = False
        for socket in list(self.user_notification_sockets[user_id]):
            try:
                await socket.send_json(message)
                sent = True
            except Exception as e:
                logger.warning(f"[WS PUSH ERROR] Socket user #{user_id} đứt ngầm: {str(e)}")
                dead_sockets.append(socket)

        # Dọn dẹp socket hỏng
        for dead in dead_sockets:
            if dead in self.user_notification_sockets.get(user_id, []):
                self.user_notification_sockets[user_id].remove(dead)
        if user_id in self.user_notification_sockets and not self.user_notification_sockets[user_id]:
            del self.user_notification_sockets[user_id]

        return sent

    def is_user_online(self, user_id: int) -> bool:
        """Kiểm tra user có đang kết nối kênh thông báo hay không."""
        return bool(self.user_notification_sockets.get(user_id))

    # --------------------------------------------------------------------------
    # TIN NHẮN CÁ NHÂN (PONG / ERROR)
    # --------------------------------------------------------------------------

    async def send_personal_message(self, websocket: WebSocket, message: dict) -> None:
        """Gửi thông điệp trực tiếp cho duy nhất socket yêu cầu."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.warning(f"[WS PERSONAL ERROR] Lỗi gửi tin cá nhân: {str(e)}")


# Singleton instance dùng chung toàn hệ thống
manager = ConnectionManager()

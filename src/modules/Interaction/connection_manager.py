from fastapi import WebSocket
from typing import Dict, List, Optional
import logging

logger = logging.getLogger("WebSocketChat")


class ConnectionManager:
    """
    Quản lý các kết nối WebSocket thời gian thực theo từng phòng hội thoại (Room-based).
    - Hỗ trợ đa kết nối: Mỗi người dùng có thể mở đồng thời nhiều tab hoặc thiết bị.
    - Dọn dẹp tài nguyên tự động: Xóa bỏ danh sách phòng khi không còn kết nối nào.
    - An toàn khi phát tán: Tự động loại bỏ socket hỏng nếu client mất mạng hoặc đóng tab.
    """
    def __init__(self):
        # Map conversation_id -> List các WebSocket đang hoạt động trong phòng đó
        self.active_rooms: Dict[int, List[WebSocket]] = {}
        # Map conversation_id -> Map websocket -> user_id (nhận diện socket thuộc user nào)
        self.socket_users: Dict[int, Dict[WebSocket, int]] = {}

    async def connect(self, conversation_id: int, websocket: WebSocket, user_id: int) -> None:
        """
        Chấp thuận kết nối WebSocket (Handshake thành công Status 101)
        và đưa socket vào danh sách phòng chat tương ứng.
        """
        await websocket.accept()
        if conversation_id not in self.active_rooms:
            self.active_rooms[conversation_id] = []
            self.socket_users[conversation_id] = {}

        self.active_rooms[conversation_id].append(websocket)
        self.socket_users[conversation_id][websocket] = user_id
        logger.info(
            f"[WS CONNECT] User #{user_id} tham gia phòng #{conversation_id}. "
            f"Tổng kết nối trong phòng: {len(self.active_rooms[conversation_id])}"
        )

    def disconnect(self, conversation_id: int, websocket: WebSocket, user_id: Optional[int] = None) -> None:
        """
        Loại bỏ kết nối khi client ngắt kết nối hoặc tắt trình duyệt.
        Nếu phòng không còn ai, xóa phòng khỏi bộ nhớ để chống Memory Leak.
        """
        if conversation_id in self.active_rooms:
            if websocket in self.active_rooms[conversation_id]:
                self.active_rooms[conversation_id].remove(websocket)

            if conversation_id in self.socket_users and websocket in self.socket_users[conversation_id]:
                del self.socket_users[conversation_id][websocket]

            # Dọn dẹp phòng rỗng
            if not self.active_rooms[conversation_id]:
                del self.active_rooms[conversation_id]
                if conversation_id in self.socket_users:
                    del self.socket_users[conversation_id]
                logger.info(f"[WS ROOM CLOSED] Phòng #{conversation_id} đã dọn dẹp do không còn ai online.")
            else:
                logger.info(
                    f"[WS DISCONNECT] User #{user_id} rời phòng #{conversation_id}. "
                    f"Còn lại: {len(self.active_rooms[conversation_id])} kết nối."
                )

    async def broadcast_to_room(self, conversation_id: int, message: dict) -> None:
        """
        Phát tán dữ liệu JSON tới tất cả các client đang online trong cùng phòng chat.
        Tự động phát hiện và loại bỏ các kết nối bị đứt ngầm.
        """
        if conversation_id not in self.active_rooms:
            return

        dead_sockets: List[WebSocket] = []
        for socket in list(self.active_rooms[conversation_id]):
            try:
                await socket.send_json(message)
            except Exception as e:
                logger.warning(f"[WS BROADCAST ERROR] Lỗi gửi socket phòng #{conversation_id}: {str(e)}")
                dead_sockets.append(socket)

        # Xử lý dọn dẹp các socket hỏng
        for dead in dead_sockets:
            uid = self.socket_users.get(conversation_id, {}).get(dead)
            self.disconnect(conversation_id, dead, uid)

    async def send_personal_message(self, websocket: WebSocket, message: dict) -> None:
        """Gửi thông điệp riêng tư (thông báo lỗi validate, phản hồi pong) cho chính socket đó."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.warning(f"[WS PERSONAL ERROR] Lỗi gửi tin cá nhân: {str(e)}")

    def is_user_in_room(self, conversation_id: int, user_id: int) -> bool:
        """Kiểm tra xem một user_id cụ thể có đang có kết nối nào trong phòng chat hay không."""
        if conversation_id not in self.socket_users:
            return False
        return user_id in self.socket_users[conversation_id].values()


# Khởi tạo Singleton instance dùng chung toàn hệ thống
manager = ConnectionManager()

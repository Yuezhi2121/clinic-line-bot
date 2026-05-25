import logging

from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    PushMessageRequest,
    TextMessage,
)

from app.config import LINE_CHANNEL_ACCESS_TOKEN

logger = logging.getLogger(__name__)

_config = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)


async def push_text(user_id: str, text: str):
    """Send a push message to a LINE user."""
    try:
        with ApiClient(_config) as api_client:
            api = MessagingApi(api_client)
            api.push_message(
                PushMessageRequest(
                    to=user_id,
                    messages=[TextMessage(text=text)],
                )
            )
    except Exception:
        logger.exception("Failed to push message to %s", user_id)


def build_update_message(
    hospital_name: str,
    doctor_name: str,
    sub_dept: str,
    current_number: int,
    appointment_number: int,
) -> str:
    """Build a notification message about progress update."""
    remaining = appointment_number - current_number

    if remaining <= 0:
        return (
            f"🔔 已經輪到你了！\n"
            f"🏥 {hospital_name}\n"
            f"{sub_dept} - {doctor_name}\n"
            f"目前看到第 {current_number} 號\n"
            f"你的號碼是 {appointment_number} 號\n"
            f"請盡速前往診間！"
        )
    elif remaining <= 3:
        return (
            f"⚡ 快輪到你了！\n"
            f"🏥 {hospital_name}\n"
            f"{sub_dept} - {doctor_name}\n"
            f"目前看到第 {current_number} 號\n"
            f"你的號碼是 {appointment_number} 號\n"
            f"前面還有 {remaining} 位！"
        )
    else:
        return (
            f"📢 看診進度更新\n"
            f"🏥 {hospital_name}\n"
            f"{sub_dept} - {doctor_name}\n"
            f"目前看到第 {current_number} 號\n"
            f"你的號碼是 {appointment_number} 號\n"
            f"前面還有 {remaining} 位"
        )

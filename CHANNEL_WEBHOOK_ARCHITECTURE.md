# Channel Webhook Architecture Analysis

## Current State

### ✅ What's Working
1. **Top-level webhook structure is channel-agnostic**
   - `WebhookMessageRequest` model supports all channels
   - Fields: `sender`, `brand_id`, `user_id`, `channel`, `message_type`, `message_body`

2. **Channel identification**
   - `channel` field identifies the source (whatsapp, gmail, telegram, etc.)
   - `channel_account_id` mapping for WhatsApp

### ❌ Current Problems

1. **Channel-specific `message_body` structure**
   - WhatsApp: `{"type": "text", "text": {"body": "Hello"}}`
   - Gmail: Would be `{"subject": "...", "body": "...", "from": "..."}`
   - Telegram: Would be `{"message": {"text": "..."}}`
   - Each channel has different structure

2. **Hardcoded WhatsApp parsing logic in multiple places**
   - `flow_service.py` (line 335-336): `message_body["text"]["body"]`
   - `user_state_service.py` (line 89-106): `_extract_user_input()` method
   - `whatsapp_flow_service.py` (line 28-45): Same WhatsApp-specific logic

3. **No abstraction for channel differences**
   - Adding a new channel requires code changes in 3+ places
   - Error-prone and hard to maintain

## Recommended Solution: Channel Adapter Pattern

### Architecture

```
Webhook Request (Channel-Specific)
    ↓
ChannelMessageAdapter.normalize_message()
    ↓
NormalizedMessage (Consistent Structure)
    ↓
Flow Processing (Channel-Agnostic)
```

### Implementation

1. **Created `ChannelMessageAdapter` service**
   - Location: `src/services/channel_message_adapter.py`
   - Normalizes all channel payloads to `NormalizedMessage` structure
   - Each channel has its own parser method

2. **NormalizedMessage Structure**
   ```python
   {
       "text": str,              # Primary text content
       "subject": str,           # Email subject
       "body": str,              # Email body
       "button_text": str,       # Button label
       "button_payload": str,    # Button payload
       "interactive_type": str,  # "button_reply", "list_reply"
       "interactive_value": str, # Interactive response value
       "media_url": str,         # Media file URL
       "media_type": str,        # "image", "video", etc.
       "raw_data": dict         # Original payload for reference
   }
   ```

3. **Benefits**
   - ✅ Single source of truth for message parsing
   - ✅ Easy to add new channels (just add a `_normalize_*` method)
   - ✅ Consistent structure for flow processing
   - ✅ Backward compatible (can still access `raw_data`)

### Migration Steps

1. **Update `webhook_service.py`**
   ```python
   # After receiving webhook, normalize message
   adapter = ChannelMessageAdapter(self.log_util)
   normalized = adapter.normalize_message(
       channel=request.channel,
       message_type=request.message_type,
       message_body=request.message_body
   )
   ```

2. **Update `flow_service.py`**
   - Replace WhatsApp-specific parsing with `normalized.get_text_content()`

3. **Update `user_state_service.py`**
   - Replace `_extract_user_input()` with normalized message access

4. **Update `whatsapp_flow_service.py`**
   - Use normalized message instead of direct `message_body` access

### Example Usage

**Before (WhatsApp-specific):**
```python
if message_type == "text":
    text_content = message_body["text"].get("body", "").strip()
```

**After (Channel-agnostic):**
```python
normalized = adapter.normalize_message(channel, message_type, message_body)
text_content = normalized.get_text_content()
```

## Alternative Approaches Considered

### Option 1: Standardize `message_body` at Webhook Entry
- **Pros**: Simpler, no adapter needed
- **Cons**: Requires all channel services to conform (not always possible)

### Option 2: Channel-Specific Services
- **Pros**: Complete isolation
- **Cons**: Code duplication, harder to maintain

### Option 3: Channel Adapter Pattern (Recommended) ✅
- **Pros**: Flexible, maintainable, extensible
- **Cons**: Slight overhead (minimal)

## Next Steps

1. ✅ Created `ChannelMessageAdapter` service
2. ⏳ Update `webhook_service.py` to use adapter
3. ⏳ Update `flow_service.py` to use normalized messages
4. ⏳ Update `user_state_service.py` to use normalized messages
5. ⏳ Update `whatsapp_flow_service.py` to use normalized messages
6. ⏳ Test with WhatsApp (backward compatibility)
7. ⏳ Test with Gmail/Email
8. ⏳ Test with Telegram

## Channel Support Status

| Channel | Parser | Status |
|---------|--------|--------|
| WhatsApp | `_normalize_whatsapp()` | ✅ Implemented |
| Gmail/Email | `_normalize_email()` | ✅ Implemented |
| Telegram | `_normalize_telegram()` | ✅ Implemented |
| SMS | `_normalize_sms()` | ✅ Implemented |
| Instagram | `_normalize_instagram()` | ✅ Implemented |
| Facebook | `_normalize_facebook()` | ✅ Implemented |
| Generic | `_normalize_generic()` | ✅ Fallback |


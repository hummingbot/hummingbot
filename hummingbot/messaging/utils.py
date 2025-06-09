

def format_composite_id_for_display(text_with_id):
    """Format composite IDs for better readability"""
    if "|" in text_with_id:
        parts = text_with_id.split("|")
        if len(parts) == 2:
            instance_id, strategy_file = parts
            formatted = f"{instance_id[:8]}|{strategy_file}"
            return formatted

    return text_with_id

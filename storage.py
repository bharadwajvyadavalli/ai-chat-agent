import json
import os
from datetime import datetime
from uuid import uuid4

class Storage:
    def __init__(self, storage_dir='storage_data'):
        self.storage_dir = storage_dir
        self.messages_file = f'{storage_dir}/messages.json'
        os.makedirs(storage_dir, exist_ok=True)
        self._init_storage()
    
    def _init_storage(self):
        if not os.path.exists(self.messages_file):
            self._save_json({'messages': []})
    
    def _load_json(self):
        try:
            with open(self.messages_file, 'r') as f:
                return json.load(f)
        except:
            return {'messages': []}
    
    def _save_json(self, data):
        with open(self.messages_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def save_message(self, role, content, tools_used=None, tools_results=None):
        """Save a message to storage"""
        data = self._load_json()
        message = {
            'id': str(uuid4()),
            'timestamp': datetime.now().isoformat(),
            'role': role,
            'content': content,
            'tools_used': tools_used or [],
            'tools_results': tools_results or {}
        }
        data['messages'].append(message)
        self._save_json(data)
    
    def get_last_messages(self, n=10):
        """Get last n messages"""
        data = self._load_json()
        return data['messages'][-n:]
    
    def get_all_messages(self):
        """Get all messages"""
        data = self._load_json()
        return data['messages']
    
    def clear(self):
        """Clear all messages"""
        self._save_json({'messages': []})

'use client';

import { useChat } from 'ai/react';
import { useEffect, useState } from 'react';
import { v4 as uuidv4 } from 'uuid';

export default function Chat() {
  const { messages, input, handleInputChange, handleSubmit } = useChat();
  const [sessionId, setSessionId] = useState('');

  useEffect(() => {
    // Set sessionId once when component mounts
    if (!sessionId) {
      setSessionId(uuidv4());
    }
  }, []);

  return (
    <div className="flex flex-col w-full max-w-md py-24 mx-auto stretch">
      {messages.map(m => (
        <div key={m.id} className="whitespace-pre-wrap">
          {m.role === 'user' ? 'User: ' : 'AI: '}
          {m.content}
        </div>
      ))}

      <form onSubmit={(e) => handleSubmit(e, { body: { sessionId } })}>
        <input
          className="fixed bottom-0 text-black w-full max-w-md p-2 mb-8 border border-gray-300 rounded shadow-xl"
          value={input}
          placeholder="Say something..."
          onChange={handleInputChange}
        />
      </form>
    </div>
  );
}

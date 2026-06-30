import { useState } from 'react';
import api from '../lib/api';

interface Message {
  id: string;
  role: 'user' | 'ai';
  content: string;
  parsedRequest?: ParsedRequest;
}

interface ParsedRequest {
  pricingGroup: string;
  objectives: string[];
  constraints: string[];
  status: 'ready' | 'running' | 'complete';
}

const PROMPT_SUGGESTIONS = [
  'Run a competitive price analysis for Electronics > Audio products',
  'Optimize pricing for Grocery category to maximize revenue',
  'Evaluate margin protection strategy for Home & Garden during supply disruption',
  'Initiate stock clearance pricing for all products below 20% inventory',
  'Analyze seasonal demand impact on Electronics > Wearables pricing',
  'Compare competitive positioning across all categories',
];

function generateId(): string {
  return `msg-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function parsePrompt(text: string): ParsedRequest {
  let pricingGroup = 'All Categories';
  let objectives: string[] = [];
  let constraints: string[] = [];

  const categoryMatch = text.match(
    /(?:for|across)\s+([\w\s&>]+?)(?:\s+(?:products|category|pricing|during|to|below))/i
  );
  if (categoryMatch) {
    pricingGroup = categoryMatch[1].trim();
  }

  if (/competitive|positioning|analysis/i.test(text)) {
    objectives.push('Competitive Positioning');
  }
  if (/revenue|maximize revenue/i.test(text)) {
    objectives.push('Revenue Maximization');
  }
  if (/margin|protection/i.test(text)) {
    objectives.push('Margin Protection');
  }
  if (/clearance|stock/i.test(text)) {
    objectives.push('Stock Clearance');
  }
  if (/seasonal|demand/i.test(text)) {
    objectives.push('Demand Forecasting');
  }
  if (/optimize/i.test(text)) {
    objectives.push('Price Optimization');
  }

  if (objectives.length === 0) {
    objectives.push('General Analysis');
  }

  if (/margin/i.test(text)) {
    constraints.push('Min margin: 15%');
  }
  if (/supply disruption/i.test(text)) {
    constraints.push('Max price change: +10%');
  }
  if (/clearance/i.test(text)) {
    constraints.push('Max discount: 40%');
  }
  if (/inventory|below \d+%/i.test(text)) {
    const inventoryMatch = text.match(/below (\d+)%/);
    constraints.push(
      `Inventory threshold: ${inventoryMatch ? inventoryMatch[1] : '20'}%`
    );
  }

  if (constraints.length === 0) {
    constraints.push('Max price change: ±15%');
    constraints.push('Min margin: 10%');
  }

  return {
    pricingGroup,
    objectives,
    constraints,
    status: 'ready',
  };
}

function ChatPricingRequest() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isThinking, setIsThinking] = useState(false);

  const handleSend = (text: string) => {
    if (!text.trim() || isThinking) return;

    const userMessage: Message = {
      id: generateId(),
      role: 'user',
      content: text.trim(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsThinking(true);

    setTimeout(() => {
      const parsed = parsePrompt(text);
      const aiMessage: Message = {
        id: generateId(),
        role: 'ai',
        content: `I've analyzed your request. Here's what I've identified:`,
        parsedRequest: parsed,
      };

      setIsThinking(false);
      setMessages((prev) => [...prev, aiMessage]);
    }, 1500);
  };

  const handleConfirmRun = async (messageId: string) => {
    setMessages((prev) =>
      prev.map((msg) =>
        msg.id === messageId && msg.parsedRequest
          ? {
              ...msg,
              parsedRequest: { ...msg.parsedRequest, status: 'running' as const },
            }
          : msg
      )
    );

    try {
      await api.post('/pricing-cycles', {
        pricingGroup:
          messages.find((m) => m.id === messageId)?.parsedRequest?.pricingGroup,
        objectives:
          messages.find((m) => m.id === messageId)?.parsedRequest?.objectives,
        constraints:
          messages.find((m) => m.id === messageId)?.parsedRequest?.constraints,
      });
    } catch {
      // Demo: proceed regardless of API availability
    }

    setTimeout(() => {
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === messageId && msg.parsedRequest
            ? {
                ...msg,
                parsedRequest: { ...msg.parsedRequest, status: 'complete' as const },
              }
            : msg
        )
      );

      const successMessage: Message = {
        id: generateId(),
        role: 'ai',
        content:
          'Pricing cycle initiated! Track progress in the Simulations tab.',
      };
      setMessages((prev) => [...prev, successMessage]);
    }, 1000);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleSend(input);
    }
  };

  return (
    <div className="flex flex-col h-[600px] border border-gray-200 rounded-lg bg-white">
      {/* Message history */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-gray-400 mt-8">
            <p className="text-lg font-medium">AI Pricing Assistant</p>
            <p className="text-sm mt-1">
              Describe your pricing strategy in natural language, or choose a
              suggestion below.
            </p>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                msg.role === 'user'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-800'
              }`}
            >
              <p className="text-sm">{msg.content}</p>

              {msg.parsedRequest && (
                <div className="mt-3 bg-white border border-gray-200 rounded-lg p-4 text-gray-800">
                  <div className="space-y-3">
                    <div>
                      <span className="text-xs font-semibold uppercase text-gray-500">
                        Pricing Group
                      </span>
                      <p className="text-sm font-medium">
                        {msg.parsedRequest.pricingGroup}
                      </p>
                    </div>

                    <div>
                      <span className="text-xs font-semibold uppercase text-gray-500">
                        Objectives
                      </span>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {msg.parsedRequest.objectives.map((obj) => (
                          <span
                            key={obj}
                            className="inline-block px-2 py-0.5 text-xs font-medium bg-blue-50 text-blue-700 rounded-full"
                          >
                            {obj}
                          </span>
                        ))}
                      </div>
                    </div>

                    <div>
                      <span className="text-xs font-semibold uppercase text-gray-500">
                        Constraints
                      </span>
                      <ul className="mt-1 space-y-0.5">
                        {msg.parsedRequest.constraints.map((c) => (
                          <li key={c} className="text-xs text-gray-600">
                            • {c}
                          </li>
                        ))}
                      </ul>
                    </div>

                    <div className="flex items-center justify-between pt-2 border-t border-gray-100">
                      <div>
                        <span className="text-xs font-semibold uppercase text-gray-500">
                          Status
                        </span>
                        <p className="text-sm font-medium text-green-600">
                          {msg.parsedRequest.status === 'ready' &&
                            'Ready to execute'}
                          {msg.parsedRequest.status === 'running' &&
                            'Executing...'}
                          {msg.parsedRequest.status === 'complete' && 'Complete'}
                        </p>
                      </div>

                      {msg.parsedRequest.status === 'ready' && (
                        <button
                          onClick={() => handleConfirmRun(msg.id)}
                          className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
                        >
                          Confirm & Run
                        </button>
                      )}

                      {msg.parsedRequest.status === 'running' && (
                        <div className="flex items-center gap-2 text-sm text-gray-500">
                          <svg
                            className="animate-spin h-4 w-4"
                            viewBox="0 0 24 24"
                            fill="none"
                          >
                            <circle
                              className="opacity-25"
                              cx="12"
                              cy="12"
                              r="10"
                              stroke="currentColor"
                              strokeWidth="4"
                            />
                            <path
                              className="opacity-75"
                              fill="currentColor"
                              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                            />
                          </svg>
                          Processing...
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {isThinking && (
          <div className="flex justify-start">
            <div className="bg-gray-100 text-gray-800 rounded-2xl px-4 py-3">
              <div className="flex items-center gap-1">
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
                <span
                  className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                  style={{ animationDelay: '0.1s' }}
                />
                <span
                  className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                  style={{ animationDelay: '0.2s' }}
                />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Prompt suggestions */}
      <div className="px-4 pb-2">
        <div className="flex flex-wrap gap-2">
          {PROMPT_SUGGESTIONS.map((suggestion) => (
            <button
              key={suggestion}
              onClick={() => handleSend(suggestion)}
              disabled={isThinking}
              className="px-3 py-1.5 text-xs font-medium text-blue-700 bg-blue-50 rounded-full hover:bg-blue-100 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {suggestion}
            </button>
          ))}
        </div>
      </div>

      {/* Input field */}
      <div className="p-4 border-t border-gray-200">
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Describe your pricing strategy..."
            disabled={isThinking}
            className="flex-1 px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-50 disabled:text-gray-400"
          />
          <button
            onClick={() => handleSend(input)}
            disabled={!input.trim() || isThinking}
            className="px-4 py-2.5 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}

export default ChatPricingRequest;

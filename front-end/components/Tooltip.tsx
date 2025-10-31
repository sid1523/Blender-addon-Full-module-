
import React from 'react';

interface TooltipProps {
  text: string;
}

const Tooltip: React.FC<TooltipProps> = ({ text }) => {
  return (
    <div className="relative group flex items-center ml-1.5">
      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-gray-500 cursor-help" viewBox="0 0 20 20" fill="currentColor">
        <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
      </svg>
      <span className="absolute bottom-full left-1/2 z-10 -translate-x-1/2 mb-2 w-max max-w-xs p-2 bg-gray-900 border border-gray-700 text-white text-xs rounded-md shadow-lg opacity-0 group-hover:opacity-100 transition-all duration-300 pointer-events-none group-hover:scale-100 scale-95">
        {text}
      </span>
    </div>
  );
};

export default Tooltip;

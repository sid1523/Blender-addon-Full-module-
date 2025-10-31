
import React, { useState, useEffect } from 'react';

const loadingMessages = [
  "Crafting your scene...",
  "Brewing procedural magic...",
  "Assembling polygons...",
  "Consulting the creative matrix...",
  "Painting with nodes...",
  "Simulating reality (almost)..."
];

const Loader: React.FC = () => {
  const [messageIndex, setMessageIndex] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setMessageIndex(prevIndex => (prevIndex + 1) % loadingMessages.length);
    }, 2000); // Change message every 2 seconds

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex flex-col items-center justify-center h-full text-center text-gray-500">
      <svg className="animate-spin h-10 w-10 text-cyan-400 mb-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
      <p className="font-semibold text-lg text-gray-400">Generating...</p>
      <p className="text-sm mt-2 min-h-[20px]">{loadingMessages[messageIndex]}</p>
    </div>
  );
};

export default Loader;

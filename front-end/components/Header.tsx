import React from 'react';

interface HeaderProps {
  onOpenGuide: () => void;
}

const Header: React.FC<HeaderProps> = ({ onOpenGuide }) => {
  return (
    <header className="bg-gray-800 shadow-lg border-b border-gray-700/50">
      <div className="container mx-auto px-4 py-4 flex justify-between items-center">
        <div className="flex items-center gap-3">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className="text-cyan-400">
                <path d="M12 22C17.5228 22 22 17.5228 22 12C22 6.47715 17.5228 2 12 2C6.47715 2 2 6.47715 2 12C2 17.5228 6.47715 22 12 22Z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                <path d="M12 2C14.5013 4.47522 15.9228 7.6433 16 11C16.082 14.5446 14.6593 17.7725 12 20.4C9.34068 17.7725 7.91797 14.5446 8 11C8.07721 7.6433 9.49866 4.47522 12 2Z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                <path d="M2 12.8333C5.392 13.4357 8.608 13.4357 12 12.8333C15.392 12.2309 18.608 12.2309 22 12.8333" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            <div>
                <h1 className="text-2xl md:text-3xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-blue-500">
                Blender World Generator
                </h1>
                <p className="mt-1 text-sm text-gray-400 hidden md:block">
                Generate procedural scene recipes for Blender using AI.
                </p>
            </div>
        </div>
        <button 
            onClick={onOpenGuide} 
            className="flex items-center gap-2 bg-gray-700/50 hover:bg-gray-700 border border-gray-600/80 text-cyan-300 font-semibold py-2 px-4 rounded-lg transition-all duration-200 hover:shadow-[0_0_15px_rgba(56,189,248,0.3)] hover:border-cyan-500/50"
            aria-label="Open prompting guide"
        >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-3a1 1 0 00-.867.5 1 1 0 11-1.731-1A3 3 0 0113 8a3.001 3.001 0 01-2 2.83V11a1 1 0 11-2 0v-1a1 1 0 011-1 1 1 0 100-2zm0 8a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
            </svg>
            <span className="hidden md:inline">Prompting Guide</span>
        </button>
      </div>
    </header>
  );
};

export default Header;

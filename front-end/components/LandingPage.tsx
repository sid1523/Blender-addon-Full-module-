import React from 'react';

interface LandingPageProps {
  onStart: () => void;
}

const LandingPage: React.FC<LandingPageProps> = ({ onStart }) => {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen text-center p-4 text-white relative overflow-hidden">
      <div className="absolute inset-0 bg-gray-900 opacity-50 z-0"></div>
      <div className="max-w-3xl z-10">
        <h1 className="text-5xl md:text-7xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-blue-500 mb-4 animate-fade-in-down">
          Craft Worlds with a Whisper
        </h1>
        <p className="text-lg md:text-xl text-gray-300 mb-8 animate-fade-in-up">
          Your AI-powered assistant for generating procedural 3D world 'recipes'. Describe your vision, and get a structured JSON file ready for your Blender scripting add-on. From vast terrains to detailed models, bring your ideas to life faster than ever.
        </p>
        <button
          onClick={onStart}
          className="bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-bold py-4 px-8 rounded-lg text-xl transition-all duration-300 transform hover:scale-110 shadow-lg shadow-cyan-500/30"
        >
          Start Creating
        </button>
      </div>
       <style>{`
        body {
            background-color: #0D1117;
            background-image:
              linear-gradient(#30363d 1px, transparent 1px),
              linear-gradient(to right, #30363d 1px, #0D1117 1px);
            background-size: 60px 60px;
            animation: bg-pan-slow 90s linear infinite;
        }
        @keyframes bg-pan-slow {
            from { background-position: 0 0; }
            to { background-position: -600px 600px; }
        }
        @keyframes fade-in-down {
          0% {
            opacity: 0;
            transform: translateY(-20px);
          }
          100% {
            opacity: 1;
            transform: translateY(0);
          }
        }
        @keyframes fade-in-up {
          0% {
            opacity: 0;
            transform: translateY(20px);
          }
          100% {
            opacity: 1;
            transform: translateY(0);
          }
        }
        .animate-fade-in-down {
          animation: fade-in-down 0.8s ease-out forwards;
        }
        .animate-fade-in-up {
          animation: fade-in-up 0.8s ease-out 0.4s forwards;
          opacity: 0;
        }
      `}</style>
    </div>
  );
};

export default LandingPage;

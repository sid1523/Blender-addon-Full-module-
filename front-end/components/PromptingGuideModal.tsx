import React from 'react';

interface PromptingGuideModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const PromptingGuideModal: React.FC<PromptingGuideModalProps> = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  return (
    <div 
      className="fixed inset-0 bg-black bg-opacity-70 z-50 flex items-center justify-center p-4 animate-fade-in"
      onClick={onClose}
    >
      <div 
        className="bg-gray-800 text-gray-300 rounded-lg shadow-2xl max-w-3xl w-full max-h-[90vh] overflow-y-auto border border-gray-700"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sticky top-0 bg-gray-800/80 backdrop-blur-sm p-5 border-b border-gray-700 flex justify-between items-center">
          <h2 className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-blue-500">
            The Perfect Prompting Guide
          </h2>
          <button onClick={onClose} className="text-gray-500 hover:text-white transition-colors text-2xl" aria-label="Close guide">
            &times;
          </button>
        </div>
        
        <div className="p-6 md:p-8 space-y-6">
          <section>
            <h3 className="text-xl font-semibold text-cyan-400 mb-2">Core Concept: The AI Recipe</h3>
            <p>This tool doesn't create the final 3D scene directly. Instead, it generates a detailed JSON "recipe". Your Blender add-on reads this recipe to construct the scene. Your goal is to make the recipe as clear and detailed as possible.</p>
          </section>

          <section>
            <h3 className="text-xl font-semibold text-cyan-400 mb-2">The Power of Specificity</h3>
            <p className="mb-3">Vague prompts lead to generic results. The more detail you provide, the closer the AI will get to your vision.</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-red-900/30 p-4 rounded-lg border border-red-700/50">
                <h4 className="font-semibold text-red-400">Vague Prompt</h4>
                <p className="text-sm italic">"A forest scene."</p>
                <p className="text-xs mt-2 text-gray-400">This might give you generic trees and a flat green ground.</p>
              </div>
              <div className="bg-green-900/30 p-4 rounded-lg border border-green-700/50">
                <h4 className="font-semibold text-green-400">Specific Prompt</h4>
                <p className="text-sm italic">"A misty, old-growth redwood forest at dawn. Sunlight filters through the canopy, creating god rays. The ground is covered in damp moss and ferns."</p>
                <p className="text-xs mt-2 text-gray-400">This tells the AI about mood, lighting, specific assets, and atmosphere.</p>
              </div>
            </div>
          </section>

          <section>
            <h3 className="text-xl font-semibold text-cyan-400 mb-2">Combine Prompt & Controls</h3>
            <p>Use the main prompt for the <strong className="text-white">overall mood, style, and atmosphere</strong>. Use the UI controls below for <strong className="text-white">specific, non-negotiable details</strong>.</p>
            <ul className="list-disc list-inside mt-2 space-y-1 text-sm">
                <li><strong className="text-gray-200">Prompt:</strong> "A lonely, windswept hill under a stormy sky."</li>
                <li><strong className="text-gray-200">Terrain Features:</strong> Add a 'dirt_path' feature to ensure a path exists.</li>
                <li><strong className="text-gray-200">Scatter Objects:</strong> Add a 'gnarled_dead_tree' to place a specific hero asset.</li>
                <li><strong className="text-gray-200">Lighting:</strong> Select the 'Overcast Gloom' preset to guarantee the right lighting.</li>
            </ul>
          </section>

          <section>
            <h3 className="text-xl font-semibold text-cyan-400 mb-2">Generating Models from Images</h3>
            <p>When you upload an image, the AI's primary goal becomes generating a 3D model of the main subject. Be clear in your prompt about what you want.</p>
             <div className="bg-gray-900/50 p-4 rounded-lg border border-gray-700 text-sm">
                <p className="italic">"Generate a low-poly, stylized 3D model of the character in this image. The model should be suitable for a mobile game."</p>
                <p className="text-xs mt-2 text-gray-400">This prompt guides the AI on both the <strong className="text-white">subject</strong> (the character) and the desired <strong className="text-white">style</strong> (low-poly, game-ready).</p>
            </div>
          </section>

          <section>
            <h3 className="text-xl font-semibold text-cyan-400 mb-2">Iterate and Refine</h3>
            <p>Don't expect the perfect result on the first try. Generate a recipe, see what the AI produced, then adjust your prompt or controls to get closer to your goal. The 'Enhance Prompt' button is a great way to get a more descriptive starting point!</p>
          </section>

        </div>
      </div>
      <style>{`
        @keyframes fade-in {
          0% { opacity: 0; }
          100% { opacity: 1; }
        }
        .animate-fade-in {
          animation: fade-in 0.3s ease-out forwards;
        }
      `}</style>
    </div>
  );
};

export default PromptingGuideModal;

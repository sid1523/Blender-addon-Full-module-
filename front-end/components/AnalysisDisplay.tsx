
import React, { useState, useEffect, useMemo } from 'react';

interface AnalysisDisplayProps {
  content: string;
}

interface CreatedObject {
  name: string;
  meshData: {
    vertices: number[][];
    faces: number[][];
    description: string;
  }
}

// Simple JSON syntax highlighter
const SyntaxHighlightedJson: React.FC<{ jsonString: string }> = ({ jsonString }) => {
  const highlightedHtml = useMemo(() => {
    let finalJsonString = jsonString;
    try {
        // Ensure it's pretty-printed
        finalJsonString = JSON.stringify(JSON.parse(jsonString), null, 2);
    } catch {
        // Not valid json, just display as is
    }

    finalJsonString = finalJsonString.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return finalJsonString.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, (match) => {
      let cls = 'text-green-400'; // number
      if (/^"/.test(match)) {
        if (/:$/.test(match)) {
          cls = 'text-cyan-400'; // key
        } else {
          cls = 'text-yellow-400'; // string
        }
      } else if (/true|false/.test(match)) {
        cls = 'text-purple-400'; // boolean
      } else if (/null/.test(match)) {
        cls = 'text-gray-500'; // null
      }
      return `<span class="${cls}">${match}</span>`;
    });
  }, [jsonString]);

  return <code className="font-mono text-sm whitespace-pre-wrap" dangerouslySetInnerHTML={{ __html: highlightedHtml }} />;
};


const AnalysisDisplay: React.FC<AnalysisDisplayProps> = ({ content }) => {
  const [copyButtonText, setCopyButtonText] = useState('Copy');

  const parsedContent = useMemo(() => {
    try {
      return JSON.parse(content);
    } catch {
      return null;
    }
  }, [content]);

  const createdObjects: CreatedObject[] | undefined = parsedContent?.objectsToCreate;

  useEffect(() => {
    setCopyButtonText('Copy');
  }, [content]);

  const handleCopy = () => {
    navigator.clipboard.writeText(JSON.stringify(parsedContent, null, 2)).then(() => {
      setCopyButtonText('Copied!');
      setTimeout(() => setCopyButtonText('Copy'), 2000);
    }).catch(err => {
      console.error('Failed to copy text: ', err);
    });
  };
  
  const handleDownload = () => {
      const blob = new Blob([JSON.stringify(parsedContent, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'blender-recipe.json';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
  };

  return (
    <div className="relative h-full flex flex-col gap-4">
      {createdObjects && createdObjects.length > 0 && (
         <div className="bg-gray-900/50 border border-cyan-700 text-cyan-200 px-4 py-3 rounded-lg text-sm shadow-lg shadow-cyan-500/10" role="alert">
            <strong className="font-bold text-base block mb-1">Generated 3D Object Found!</strong>
            {createdObjects.map((obj, index) => (
                <div key={index} className="mb-2 last:mb-0">
                    <p><strong>{obj.name || `Object ${index + 1}`}:</strong> Contains {obj.meshData?.vertices?.length || 0} vertices and {obj.meshData?.faces?.length || 0} faces.</p>
                </div>
            ))}
             <p className="mt-2 text-xs text-cyan-300/80"><strong>Instructions:</strong> Your Blender script can parse this JSON. Use the `vertices` and `faces` arrays from the `meshData` to create a new mesh object using `bpy.data.meshes.new()` and `new_mesh.from_pydata()`.</p>
         </div>
      )}
      <div className="relative flex-grow min-h-0">
          <div className="absolute top-2 right-2 z-10 flex gap-2">
            <button
                onClick={handleDownload}
                className="bg-gray-700 hover:bg-cyan-600 text-white font-semibold py-1 px-3 rounded-md text-sm transition-colors duration-200 flex items-center gap-1.5"
                aria-label="Download JSON file"
            >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clipRule="evenodd" /></svg>
                Download
            </button>
            <button
                onClick={handleCopy}
                className="bg-gray-700 hover:bg-cyan-600 text-white font-semibold py-1 px-3 rounded-md text-sm transition-colors duration-200 flex items-center gap-1.5"
                aria-label="Copy JSON to clipboard"
            >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor"><path d="M7 9a2 2 0 012-2h6a2 2 0 012 2v6a2 2 0 01-2 2H9a2 2 0 01-2-2V9z" /><path d="M4 3a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2V5a2 2 0 00-2-2H4z" /></svg>
                {copyButtonText}
            </button>
          </div>
          <pre className="bg-gray-900 rounded-md p-4 h-full overflow-auto border border-gray-700">
             <SyntaxHighlightedJson jsonString={content} />
          </pre>
      </div>
    </div>
  );
};

export default AnalysisDisplay;

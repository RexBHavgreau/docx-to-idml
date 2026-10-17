import { useState, useCallback } from 'react';
import { parseDocx, type DocxContent } from './utils/docxParser';
import { generateIdml } from './utils/idmlGenerator';
import { FileText, Upload, Download, CheckCircle, AlertCircle, Loader2, FileOutput, ArrowRight, Info } from 'lucide-react';

type AppState = 'idle' | 'parsing' | 'parsed' | 'converting' | 'done' | 'error';

export default function App() {
  const [state, setState] = useState<AppState>('idle');
  const [docxContent, setDocxContent] = useState<DocxContent | null>(null);
  const [fileName, setFileName] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const [idmlBlob, setIdmlBlob] = useState<Blob | null>(null);
  const [dragActive, setDragActive] = useState(false);

  const handleFile = useCallback(async (file: File) => {
    if (!file.name.toLowerCase().endsWith('.docx')) {
      setState('error');
      setErrorMsg('Please select a .docx file');
      return;
    }

    setFileName(file.name);
    setState('parsing');
    setErrorMsg('');

    try {
      const content = await parseDocx(file);
      setDocxContent(content);
      setState('parsed');
    } catch (err) {
      setState('error');
      setErrorMsg(err instanceof Error ? err.message : 'Failed to parse DOCX file');
    }
  }, []);

  const handleConvert = useCallback(async () => {
    if (!docxContent) return;

    setState('converting');
    try {
      const blob = await generateIdml(docxContent);
      setIdmlBlob(blob);
      setState('done');
    } catch (err) {
      setState('error');
      setErrorMsg(err instanceof Error ? err.message : 'Failed to generate IDML file');
    }
  }, [docxContent]);

  const handleDownload = useCallback(() => {
    if (!idmlBlob) return;
    const url = URL.createObjectURL(idmlBlob);
    const a = document.createElement('a');
    a.href = url;
    a.download = fileName.replace('.docx', '.idml');
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [idmlBlob, fileName]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }, [handleFile]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
  }, []);

  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  }, [handleFile]);

  const reset = useCallback(() => {
    setState('idle');
    setDocxContent(null);
    setFileName('');
    setErrorMsg('');
    setIdmlBlob(null);
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-950 to-slate-900 text-white">
      {/* Header */}
      <header className="border-b border-white/10 backdrop-blur-sm">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
              <FileOutput className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold">DOCX → IDML Converter</h1>
              <p className="text-xs text-slate-400">Convert Word documents to InDesign Markup Language</p>
            </div>
          </div>
          {state !== 'idle' && (
            <button
              onClick={reset}
              className="px-4 py-2 text-sm rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 transition-colors"
            >
              Start Over
            </button>
          )}
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-12">
        {/* Upload Area */}
        {state === 'idle' && (
          <div className="max-w-2xl mx-auto">
            <div className="text-center mb-8">
              <h2 className="text-3xl font-bold mb-3">Convert DOCX to IDML</h2>
              <p className="text-slate-400 text-lg">
                Transform your Word documents into Adobe InDesign Markup Language files
              </p>
            </div>

            <div
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              className={`
                relative border-2 border-dashed rounded-2xl p-12 text-center transition-all duration-300
                ${dragActive
                  ? 'border-purple-400 bg-purple-500/10 scale-[1.02]'
                  : 'border-white/20 hover:border-purple-400/50 hover:bg-white/5'
                }
              `}
            >
              <input
                type="file"
                accept=".docx"
                onChange={handleInputChange}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
              />
              <div className="flex flex-col items-center gap-4">
                <div className={`w-16 h-16 rounded-full flex items-center justify-center transition-colors ${dragActive ? 'bg-purple-500/20' : 'bg-white/5'}`}>
                  <Upload className={`w-8 h-8 ${dragActive ? 'text-purple-400' : 'text-slate-400'}`} />
                </div>
                <div>
                  <p className="text-lg font-medium">
                    {dragActive ? 'Drop your file here' : 'Drag & drop your DOCX file'}
                  </p>
                  <p className="text-sm text-slate-400 mt-1">or click to browse</p>
                </div>
                <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-white/5 border border-white/10">
                  <FileText className="w-4 h-4 text-blue-400" />
                  <span className="text-sm text-slate-300">.docx files supported</span>
                </div>
              </div>
            </div>

            {/* Info Section */}
            <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-4">
              <InfoCard
                icon={<FileText className="w-5 h-5 text-blue-400" />}
                title="DOCX Input"
                description="Upload Microsoft Word documents with text, styles, and formatting"
              />
              <InfoCard
                icon={<ArrowRight className="w-5 h-5 text-purple-400" />}
                title="Smart Conversion"
                description="Maps Word styles to InDesign paragraph and character styles"
              />
              <InfoCard
                icon={<FileOutput className="w-5 h-5 text-pink-400" />}
                title="IDML Output"
                description="Get a valid IDML package ready to open in Adobe InDesign"
              />
            </div>
          </div>
        )}

        {/* Parsing State */}
        {state === 'parsing' && (
          <div className="max-w-md mx-auto text-center py-20">
            <Loader2 className="w-12 h-12 text-purple-400 animate-spin mx-auto mb-4" />
            <p className="text-lg font-medium">Parsing {fileName}...</p>
            <p className="text-sm text-slate-400 mt-2">Extracting text and styles from your document</p>
          </div>
        )}

        {/* Parsed - Preview & Convert */}
        {state === 'parsed' && docxContent && (
          <div className="max-w-4xl mx-auto">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <CheckCircle className="w-6 h-6 text-green-400" />
                <div>
                  <p className="font-medium text-lg">{fileName}</p>
                  <p className="text-sm text-slate-400">Successfully parsed • {docxContent.paragraphs.length} paragraphs • {docxContent.styles.length} styles</p>
                </div>
              </div>
              <button
                onClick={handleConvert}
                className="px-6 py-3 rounded-xl bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 font-medium transition-all hover:scale-105 shadow-lg shadow-purple-500/25"
              >
                Convert to IDML
              </button>
            </div>

            {/* Document Preview */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Content Preview */}
              <div className="bg-white/5 rounded-2xl border border-white/10 overflow-hidden">
                <div className="px-5 py-3 border-b border-white/10 flex items-center gap-2">
                  <FileText className="w-4 h-4 text-blue-400" />
                  <span className="text-sm font-medium">Document Content</span>
                </div>
                <div className="p-5 max-h-96 overflow-y-auto">
                  {docxContent.paragraphs.slice(0, 30).map((para, i) => (
                    <div key={i} className="mb-3">
                      <p className={`text-sm ${
                        para.style.toLowerCase().includes('heading1') || para.style === '1' ? 'text-xl font-bold text-purple-300' :
                        para.style.toLowerCase().includes('heading2') || para.style === '2' ? 'text-lg font-bold text-purple-200' :
                        para.style.toLowerCase().includes('heading3') || para.style === '3' ? 'text-base font-bold text-purple-100' :
                        para.style.toLowerCase().includes('title') ? 'text-2xl font-bold text-white' :
                        'text-slate-300'
                      } ${para.alignment === 'center' ? 'text-center' : ''} ${para.alignment === 'right' ? 'text-right' : ''}`}>
                        {para.text || <span className="text-slate-600 italic">[empty]</span>}
                      </p>
                    </div>
                  ))}
                  {docxContent.paragraphs.length > 30 && (
                    <p className="text-sm text-slate-500 text-center mt-4">
                      ... and {docxContent.paragraphs.length - 30} more paragraphs
                    </p>
                  )}
                </div>
              </div>

              {/* Styles Preview */}
              <div className="bg-white/5 rounded-2xl border border-white/10 overflow-hidden">
                <div className="px-5 py-3 border-b border-white/10 flex items-center gap-2">
                  <Info className="w-4 h-4 text-purple-400" />
                  <span className="text-sm font-medium">Document Info</span>
                </div>
                <div className="p-5 max-h-96 overflow-y-auto">
                  <div className="space-y-4">
                    <div>
                      <p className="text-xs uppercase tracking-wider text-slate-500 mb-2">Title</p>
                      <p className="text-sm font-medium">{docxContent.title}</p>
                    </div>
                    <div>
                      <p className="text-xs uppercase tracking-wider text-slate-500 mb-2">Statistics</p>
                      <div className="grid grid-cols-2 gap-2">
                        <Stat label="Paragraphs" value={docxContent.paragraphs.length} />
                        <Stat label="Styles" value={docxContent.styles.length} />
                        <Stat label="Fonts" value={docxContent.fonts.size} />
                        <Stat label="Text Runs" value={docxContent.paragraphs.reduce((acc, p) => acc + p.runs.length, 0)} />
                      </div>
                    </div>
                    <div>
                      <p className="text-xs uppercase tracking-wider text-slate-500 mb-2">Fonts Used</p>
                      <div className="flex flex-wrap gap-2">
                        {Array.from(docxContent.fonts).map(font => (
                          <span key={font} className="px-2 py-1 text-xs rounded-md bg-white/5 border border-white/10">
                            {font}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div>
                      <p className="text-xs uppercase tracking-wider text-slate-500 mb-2">Paragraph Styles</p>
                      <div className="flex flex-wrap gap-2">
                        {Array.from(new Set(docxContent.paragraphs.map(p => p.style))).map(style => (
                          <span key={style} className="px-2 py-1 text-xs rounded-md bg-purple-500/10 border border-purple-500/20 text-purple-300">
                            {style}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Converting State */}
        {state === 'converting' && (
          <div className="max-w-md mx-auto text-center py-20">
            <Loader2 className="w-12 h-12 text-purple-400 animate-spin mx-auto mb-4" />
            <p className="text-lg font-medium">Generating IDML package...</p>
            <p className="text-sm text-slate-400 mt-2">Creating InDesign-compatible XML structure</p>
          </div>
        )}

        {/* Done State */}
        {state === 'done' && idmlBlob && (
          <div className="max-w-2xl mx-auto text-center">
            <div className="bg-white/5 rounded-2xl border border-white/10 p-12">
              <div className="w-20 h-20 rounded-full bg-green-500/10 flex items-center justify-center mx-auto mb-6">
                <CheckCircle className="w-10 h-10 text-green-400" />
              </div>
              <h2 className="text-2xl font-bold mb-2">Conversion Complete!</h2>
              <p className="text-slate-400 mb-2">
                Your IDML file is ready for download
              </p>
              <p className="text-sm text-slate-500 mb-8">
                {(idmlBlob.size / 1024).toFixed(1)} KB • {fileName.replace('.docx', '.idml')}
              </p>
              <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                <button
                  onClick={handleDownload}
                  className="px-8 py-3 rounded-xl bg-gradient-to-r from-green-500 to-emerald-500 hover:from-green-600 hover:to-emerald-600 font-medium transition-all hover:scale-105 shadow-lg shadow-green-500/25 flex items-center gap-2"
                >
                  <Download className="w-5 h-5" />
                  Download IDML File
                </button>
                <button
                  onClick={reset}
                  className="px-6 py-3 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 font-medium transition-colors"
                >
                  Convert Another File
                </button>
              </div>

              <div className="mt-8 p-4 rounded-xl bg-white/5 border border-white/10 text-left">
                <p className="text-xs uppercase tracking-wider text-slate-500 mb-2">What's included</p>
                <ul className="text-sm text-slate-300 space-y-1">
                  <li>✓ Text content with paragraph styles</li>
                  <li>✓ Character formatting (bold, italic, underline)</li>
                  <li>✓ Font information</li>
                  <li>✓ Text alignment</li>
                  <li>✓ Valid IDML package structure</li>
                </ul>
              </div>
            </div>
          </div>
        )}

        {/* Error State */}
        {state === 'error' && (
          <div className="max-w-md mx-auto text-center py-20">
            <div className="w-16 h-16 rounded-full bg-red-500/10 flex items-center justify-center mx-auto mb-4">
              <AlertCircle className="w-8 h-8 text-red-400" />
            </div>
            <p className="text-lg font-medium text-red-300 mb-2">Conversion Failed</p>
            <p className="text-sm text-slate-400 mb-6">{errorMsg}</p>
            <button
              onClick={reset}
              className="px-6 py-3 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 font-medium transition-colors"
            >
              Try Again
            </button>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-white/10 mt-auto">
        <div className="max-w-6xl mx-auto px-6 py-6 text-center text-sm text-slate-500">
          <p>DOCX to IDML Converter • Converts Word documents to Adobe InDesign Markup Language</p>
          <p className="mt-1 text-xs">All processing happens locally in your browser. No files are uploaded to any server.</p>
        </div>
      </footer>
    </div>
  );
}

function InfoCard({ icon, title, description }: { icon: React.ReactNode; title: string; description: string }) {
  return (
    <div className="p-5 rounded-xl bg-white/5 border border-white/10 hover:bg-white/[0.07] transition-colors">
      <div className="flex items-center gap-3 mb-2">
        {icon}
        <span className="font-medium text-sm">{title}</span>
      </div>
      <p className="text-xs text-slate-400">{description}</p>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="p-2 rounded-lg bg-white/5 border border-white/10">
      <p className="text-lg font-bold text-white">{value}</p>
      <p className="text-xs text-slate-400">{label}</p>
    </div>
  );
}

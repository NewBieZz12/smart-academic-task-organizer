'use client';
import React, { useState } from 'react';

interface OnboardingModalProps {
  isOpen: boolean;
  projectName: string;
  projectId?: string;
  onClose: () => void;
  onUploadSuccess: () => void;
}

const normalizeProjectId = (projectId?: string) => {
  const cleaned = String(projectId || '').trim();
  return cleaned.length > 0 ? cleaned : 'project-1';
};

export default function OnboardingModal({
  isOpen,
  projectName,
  projectId = 'project-1',
  onClose,
  onUploadSuccess
}: OnboardingModalProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  if (!isOpen) return null;

  const activeProjectId = normalizeProjectId(projectId);

  // Handles the timetable file upload to the FastAPI backend.
  const handleFileUpload = async (file: File) => {
    if (!file.type.startsWith('image/')) {
      setErrorMessage('Unsupported asset type. Please select a valid image snapshot format.');
      return;
    }

    setErrorMessage('');
    setIsUploading(true);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('project_id', activeProjectId);

    try {
      const response = await fetch('http://127.0.0.1:8000/api/upload-timetable', {
        method: 'POST',
        body: formData,
      });

      let result: any = {};
      try {
        result = await response.json();
      } catch {
        result = {};
      }

      if (response.ok && result.success) {
        console.log('Success! Backend parsed timetable data:', result);
        onUploadSuccess();
        onClose();
      } else {
        setErrorMessage(
          result.detail ||
          result.message ||
          "OCR completed but couldn't isolate academic tags."
        );
      }
    } catch (error) {
      console.error('Upload error:', error);
      setErrorMessage('Network loss detected: Could not establish a connection to processing backend.');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-md p-4 animate-fade-in">
      <div className="bg-white w-full max-w-md rounded-2xl shadow-2xl border border-slate-100 p-8 flex flex-col items-center text-center animate-scale-up">

        <div className="w-12 h-12 bg-blue-50 text-blue-600 rounded-full flex items-center justify-center text-xl font-bold mb-4 border border-blue-100 shadow-sm">
          {isUploading ? '⏳' : '1'}
        </div>

        <h3 className="text-xl font-bold text-slate-800">
          {isUploading ? 'Processing...' : `Initialize ${projectName}`}
        </h3>

        <p className="text-sm text-slate-500 mt-2 max-w-xs">
          {isUploading
            ? 'Our Smart System is extracting classes from your timetable...'
            : 'Please upload your semester timetable image.'}
        </p>


        <div
          onDragOver={(e) => {
            e.preventDefault();
            if (!isUploading) setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setIsDragging(false);

            if (e.dataTransfer.files && e.dataTransfer.files[0] && !isUploading) {
              handleFileUpload(e.dataTransfer.files[0]);
            }
          }}
          className={`w-full border-2 border-dashed rounded-xl p-8 mt-6 flex flex-col items-center justify-center transition-all ${
            isDragging
              ? 'border-blue-500 bg-blue-50/50'
              : 'border-slate-200 bg-slate-50/50'
          }`}
        >
          {isUploading ? (
            <div className="animate-pulse text-blue-500 font-bold">Parsing in progress...</div>
          ) : (
            <>
              <p className="text-sm font-semibold text-slate-700">Drag & Drop Timetable Image</p>

              <input
                type="file"
                className="hidden"
                id={`fileInput-${activeProjectId}`}
                accept="image/*"
                onChange={(e) => {
                  if (e.target.files && e.target.files[0]) {
                    handleFileUpload(e.target.files[0]);
                  }
                }}
              />

              <label
                htmlFor={`fileInput-${activeProjectId}`}
                className="mt-4 px-4 py-1.5 bg-white text-slate-700 border border-slate-200 rounded-lg text-xs font-medium shadow-sm hover:bg-gray-50 cursor-pointer"
              >
                Select File
              </label>
            </>
          )}
        </div>

        {errorMessage && (
          <div className="w-full text-xs bg-red-50 text-red-600 border border-red-100 p-2.5 rounded-xl mt-4 font-medium">
            ⚠️ {errorMessage}
          </div>
        )}

        <div className="w-full flex justify-end mt-6 border-t pt-4">
          <button
            onClick={onClose}
            className="text-xs font-semibold text-slate-400 hover:text-slate-600 transition disabled:opacity-40"
            disabled={isUploading}
          >
          </button>
        </div>
      </div>
    </div>
  );
}

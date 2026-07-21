'use client';
import React from 'react';
import { ProjectWorkspace } from '../types/scheduler';

interface SidebarProps {
  projects: ProjectWorkspace[];
  activeProjectId: string;
  onSelectProject: (id: string) => void;
  onCreateNewProject: () => void;
  onDeleteProject: (id: string) => void;
}

export default function Sidebar({
  projects,
  activeProjectId,
  onSelectProject,
  onCreateNewProject,
  onDeleteProject,
}: SidebarProps) {
  return (
    <aside className="w-64 bg-slate-900 text-slate-100 flex flex-col h-screen border-r border-slate-800">
      {/* Workspace App Branding Header */}
      <div className="p-6 border-b border-slate-800">
        <h1 className="text-xl font-bold bg-gradient-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent">
          Smart Academic Task Organizer
        </h1>
        <p className="text-xs text-slate-400 mt-1">HEE WEI JIE SWE2304437</p>
      </div>

      {/* Dynamic Active Projects/Timetables Stream List */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="flex items-center justify-between px-2 mb-3">
          <span className="text-xs font-semibold text-slate-400 tracking-wider uppercase">
            Active Timetable
          </span>
        </div>

        <div className="space-y-1">
          {projects.map((project) => {
            const isActive = project.id === activeProjectId;

            return (
              <div
                key={project.id}
                className={`w-full flex items-center justify-between rounded-lg transition-colors ${
                  isActive
                    ? 'bg-blue-600 text-white'
                    : 'text-slate-300 hover:bg-slate-800 hover:text-slate-100'
                }`}
              >
                <button
                  onClick={() => onSelectProject(project.id)}
                  className="flex-1 flex items-center justify-between px-3 py-2.5 text-sm font-medium text-left"
                >
                  <span className="flex items-center gap-2.5 truncate">
                    {project.name}
                  </span>

                  {!project.isTimetableLoaded && (
                    <span className="text-[10px] bg-amber-500/20 text-amber-400 border border-amber-500/30 px-2 py-0.5 rounded-md font-normal ml-2 shrink-0">
                      Setup Needed
                    </span>
                  )}
                </button>

                <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();

                  const confirmDelete = window.confirm(
                    `Are you sure you want to delete "${project.name}"? All timetable, tasks, chat history, and schedule records for this timetable will be removed.`
                  );

                  if (confirmDelete) {
                    onDeleteProject(project.id);
                  }
                }}
                className={`mr-2 px-2 py-1 rounded-md text-xs font-semibold transition-colors ${
                  isActive
                    ? 'text-red-200 hover:bg-red-700/30 hover:text-red-100'
                    : 'text-red-500 hover:bg-red-500/20 hover:text-red-400'
                }`}
                title={`Delete ${project.name}`}
              >
                DELETE
              </button>
              </div>
            );
          })}
        </div>
      </div>

      {/* Persistent New Project Trigger Action Button */}
      <div className="p-4 border-t border-slate-800">
        <button
          onClick={onCreateNewProject}
          className="w-full bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-medium py-2.5 px-4 rounded-xl transition-all border border-slate-700 hover:border-slate-600 flex items-center justify-center gap-2"
        >
          <span>➕</span> New Timetable
        </button>
      </div>
    </aside>
  );
}
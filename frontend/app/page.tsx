// page.tsx
'use client';


import React, { useState, useEffect, useCallback } from 'react';
import Sidebar from '../components/Sidebar';
import OnboardingModal from '../components/OnboardingModal';
import TimetableGrid from '../components/TimetableGrid';
import ChatContainer from '../components/ChatContainer';
import CalendarView from '../components/CalendarView';
import { ProjectWorkspace, ViewMode } from '../types/scheduler';


interface Assignment {
 id?: number;
 project_id?: string;
 course_code: string;
 course_name: string;
 assessment_title: string;
 deadline_iso: string;
 priority: string;
 sorting_score: number;
 isDbRecord?: boolean;
 rawTaskId?: string | number;
}


const API_BASE_URL = 'http://127.0.0.1:8000';


const PROJECTS_STORAGE_KEY = 'smart_academic_projects';
const ACTIVE_PROJECT_STORAGE_KEY = 'smart_academic_active_project';


const DEFAULT_PROJECTS: ProjectWorkspace[] = [
 { id: 'project-1', name: 'Timetable 1', isTimetableLoaded: false },
 { id: 'project-2', name: 'Timetable 2', isTimetableLoaded: false },
];


const normalizeProjectId = (projectId?: string) => {
 const cleaned = String(projectId || '').trim();
 return cleaned.length > 0 ? cleaned : 'project-1';
};


const generateNextProjectInfo = (projects: ProjectWorkspace[]) => {
 let nextIndex = projects.length + 1;
 let nextProjectId = `project-${nextIndex}`;


 const existingIds = new Set(projects.map(project => project.id));


 while (existingIds.has(nextProjectId)) {
   nextIndex += 1;
   nextProjectId = `project-${nextIndex}`;
 }


 return {
   id: nextProjectId,
   name: `Timetable ${nextIndex}`,
 };
};


export default function Page() {
 const [projects, setProjects] = useState<ProjectWorkspace[]>(DEFAULT_PROJECTS);
 const [activeProjectId, setActiveProjectId] = useState<string>('project-1');
 const [currentView, setCurrentView] = useState<ViewMode>('timetable');
 const [isExporting, setIsExporting] = useState<boolean>(false);


 // Prevent localStorage from being overwritten before it is loaded.
 const [isStorageReady, setIsStorageReady] = useState<boolean>(false);


 // Module 2 + Module 3 saved tasks / assignment deadlines / generated study tasks
 const [dbAssignmentsMap, setDbAssignmentsMap] = useState<{ [projectId: string]: any[] }>({});


 // This key is used to force TimetableGrid to remount/refetch after timetable upload.
 const [timetableRefreshKey, setTimetableRefreshKey] = useState<number>(0);


 const safeActiveProjectId = normalizeProjectId(activeProjectId);
 const dbAssignments = dbAssignmentsMap[safeActiveProjectId] || [];
 const activeProject = projects.find((p) => p.id === safeActiveProjectId);


 // Load saved projects and active timetable after refresh.
 useEffect(() => {
   if (typeof window === 'undefined') return;


   try {
     const savedProjectsRaw = window.localStorage.getItem(PROJECTS_STORAGE_KEY);
     const savedActiveProjectId = window.localStorage.getItem(ACTIVE_PROJECT_STORAGE_KEY);


     let loadedProjects: ProjectWorkspace[] = DEFAULT_PROJECTS;


     if (savedProjectsRaw) {
       const parsedProjects = JSON.parse(savedProjectsRaw);


       if (Array.isArray(parsedProjects) && parsedProjects.length > 0) {
         loadedProjects = parsedProjects.map((project: any, index: number) => ({
           id: normalizeProjectId(project.id || `project-${index + 1}`),
           name: project.name || `Timetable ${index + 1}`,
           isTimetableLoaded: Boolean(project.isTimetableLoaded),
         }));
       }
     }


     setProjects(loadedProjects);


     const activeIdIsValid =
       savedActiveProjectId &&
       loadedProjects.some(project => project.id === savedActiveProjectId);


     if (activeIdIsValid) {
       setActiveProjectId(savedActiveProjectId);
     } else {
       setActiveProjectId(loadedProjects[0]?.id || 'project-1');
     }
   } catch (err) {
     console.error('❌ Failed to load saved timetable workspaces:', err);


     setProjects(DEFAULT_PROJECTS);
     setActiveProjectId('project-1');
   } finally {
     setIsStorageReady(true);
   }
 }, []);


 // Save projects and active project whenever they change.
 useEffect(() => {
   if (!isStorageReady || typeof window === 'undefined') return;


   try {
     window.localStorage.setItem(PROJECTS_STORAGE_KEY, JSON.stringify(projects));
     window.localStorage.setItem(ACTIVE_PROJECT_STORAGE_KEY, safeActiveProjectId);
   } catch (err) {
     console.error('❌ Failed to save timetable workspaces:', err);
   }
 }, [projects, safeActiveProjectId, isStorageReady]);


 const checkGlobalTimetableStatus = useCallback(async () => {
   try {
     console.log(`🔍 Syncing timetable status for workspace: ${safeActiveProjectId}`);


     const response = await fetch(
       `${API_BASE_URL}/api/timetable-status?project_id=${encodeURIComponent(safeActiveProjectId)}`
     );


     if (!response.ok) {
       throw new Error(`Status check API unreachable. HTTP ${response.status}`);
     }


     const payload = await response.json();


     setProjects(prev =>
       prev.map(p =>
         p.id === safeActiveProjectId
           ? { ...p, isTimetableLoaded: Boolean(payload.success && payload.has_timetable) }
           : p
       )
     );
   } catch (err) {
     console.error('❌ System state analyzer failed to query tracking routes:', err);
   }
 }, [safeActiveProjectId]);


 const fetchUpdatedDashboardTasks = useCallback(async () => {
   try {
     console.log(`📡 Fetching committed database tracks for workspace: ${safeActiveProjectId}`);


     const response = await fetch(
       `${API_BASE_URL}/api/schedule/tasks?project_id=${encodeURIComponent(safeActiveProjectId)}`
     );


     if (!response.ok) {
       throw new Error(`Core API network response failure status: ${response.status}`);
     }


     const serverPayload = await response.json();


     setDbAssignmentsMap(prev => ({
       ...prev,
       [safeActiveProjectId]:
         serverPayload.success && Array.isArray(serverPayload.tasks)
           ? serverPayload.tasks
           : []
     }));
   } catch (err) {
     console.error('❌ Failed to resolve task syncing from SQLite layer:', err);


     setDbAssignmentsMap(prev => ({
       ...prev,
       [safeActiveProjectId]: []
     }));
   }
 }, [safeActiveProjectId]);


 useEffect(() => {
   if (!isStorageReady) return;


   checkGlobalTimetableStatus();
   fetchUpdatedDashboardTasks();
 }, [
   isStorageReady,
   safeActiveProjectId,
   checkGlobalTimetableStatus,
   fetchUpdatedDashboardTasks
 ]);
 const handleDeleteAssignmentLog = async (targetTask: Assignment) => {
   const taskId = targetTask.rawTaskId ?? targetTask.id;


   if (!taskId) {
     console.error('❌ Cannot delete DB assignment because task id is missing:', targetTask);
     return;
   }


   try {
     console.log(`🗑️ Deleting task ${taskId} under workspace: ${safeActiveProjectId}`);


     const response = await fetch(
       `${API_BASE_URL}/api/schedule/tasks/${encodeURIComponent(String(taskId))}?project_id=${encodeURIComponent(safeActiveProjectId)}`,
       {
         method: 'DELETE',
       }
     );


     const result = await response.json().catch(() => ({}));


     if (!response.ok) {
       throw new Error(
         result.detail ||
         result.message ||
         `Backend deletion rejection status: ${response.status}`
       );
     }


     if (result.success) {
       await fetchUpdatedDashboardTasks();
     }
   } catch (err) {
     console.error('❌ Drop sequence exception fault on SQLite boundary:', err);


     setDbAssignmentsMap(prev => ({
       ...prev,
       [safeActiveProjectId]: (prev[safeActiveProjectId] || []).filter(
         task => String(task.id) !== String(taskId)
       )
     }));
   }
 };


 const handleExportTimetableImage = async () => {
   setIsExporting(true);


   try {
     const response = await fetch(
       `${API_BASE_URL}/api/export-timetable-image?project_id=${encodeURIComponent(safeActiveProjectId)}`,
       {
         method: 'GET',
       }
     );


     if (!response.ok) {
       const errorData = await response.json().catch(() => ({}));
       throw new Error(errorData.detail || 'Could not generate export canvas file.');
     }


     const imageBlob = await response.blob();
     const downloadUrl = window.URL.createObjectURL(imageBlob);
     const tempAnchor = document.createElement('a');


     tempAnchor.href = downloadUrl;
     tempAnchor.download = `${activeProject?.name || 'timetable'}_export.jpg`;


     document.body.appendChild(tempAnchor);
     tempAnchor.click();
     document.body.removeChild(tempAnchor);
     window.URL.revokeObjectURL(downloadUrl);
   } catch (err: any) {
     console.error('❌ Image export execution failed:', err);
     alert(err.message || 'Something went wrong compiling your export file.');
   } finally {
     setIsExporting(false);
   }
 };


 const handleDeleteProject = async (projectIdToDelete: string) => {
   const normalizedDeleteId = normalizeProjectId(projectIdToDelete);
   const targetProject = projects.find(project => project.id === normalizedDeleteId);


   if (!targetProject) {
     alert('Selected timetable workspace was not found.');
     return;
   }


   if (projects.length <= 1) {
     const confirmOnlyProjectDelete = window.confirm(
       `Are you sure you want to delete "${targetProject.name}"? This is your last timetable. A new empty Timetable 1 will be created after deletion.`
     );


     if (!confirmOnlyProjectDelete) return;
   }


   try {
     console.log(`🗑️ Deleting full timetable workspace: ${normalizedDeleteId}`);


     const response = await fetch(
       `${API_BASE_URL}/api/delete-workspace/${encodeURIComponent(normalizedDeleteId)}`,
       {
         method: 'DELETE',
       }
     );


     const result = await response.json().catch(() => ({}));


     if (!response.ok) {
       throw new Error(
         result.detail ||
         result.message ||
         `Workspace deletion rejected by backend. HTTP ${response.status}`
       );
     }


     const remainingProjects = projects.filter(project => project.id !== normalizedDeleteId);


     // Remove chat/module localStorage records owned by the deleted timetable.
     window.localStorage.removeItem(`chat_history_${normalizedDeleteId}`);
     window.localStorage.removeItem(`chat_course_blocks_${normalizedDeleteId}`);
     window.localStorage.removeItem(`chat_assignment_summaries_${normalizedDeleteId}`);
     window.localStorage.removeItem(`chat_saved_task_registry_${normalizedDeleteId}`);


     // Remove cached DB task map for this timetable.
     setDbAssignmentsMap(prev => {
       const next = { ...prev };
       delete next[normalizedDeleteId];
       return next;
     });


     if (remainingProjects.length > 0) {
       setProjects(remainingProjects);


       if (safeActiveProjectId === normalizedDeleteId) {
         setActiveProjectId(remainingProjects[0].id);
         setCurrentView('timetable');
       }
     } else {
       const defaultProject: ProjectWorkspace = {
         id: 'project-1',
         name: 'Timetable 1',
         isTimetableLoaded: false,
       };


       setProjects([defaultProject]);
       setActiveProjectId(defaultProject.id);
       setCurrentView('timetable');
     }


     setTimetableRefreshKey(prev => prev + 1);
   } catch (err: any) {
     console.error('❌ Failed to delete timetable workspace:', err);
     alert(err.message || 'Failed to delete timetable workspace.');
   }
 };


 const handleCreateNewProject = () => {
   const nextProjectInfo = generateNextProjectInfo(projects);


   const newProject: ProjectWorkspace = {
     id: nextProjectInfo.id,
     name: nextProjectInfo.name,
     isTimetableLoaded: false,
   };


   setDbAssignmentsMap(prev => ({ ...prev, [newProject.id]: [] }));


   setProjects(prev => [...prev, newProject]);
   setActiveProjectId(newProject.id);
   setCurrentView('timetable');


   // Reset timetable view state for new project.
   // Because isTimetableLoaded is false, OnboardingModal will pop out immediately.
   setTimetableRefreshKey(prev => prev + 1);
 };


 const handleSelectProject = (projectId: string) => {
   const selectedProjectId = normalizeProjectId(projectId);


   setActiveProjectId(selectedProjectId);
   setCurrentView('timetable');
   setTimetableRefreshKey(prev => prev + 1);
 };


 const handleOnboardingSuccess = async () => {
   setProjects(prevProjects =>
     prevProjects.map(p =>
       p.id === safeActiveProjectId ? { ...p, isTimetableLoaded: true } : p
     )
   );


   // OnboardingModal uploads the timetable.
   // TimetableGrid fetches the updated timetable from backend.
   // This key forces TimetableGrid to remount and refetch after upload.
   setTimetableRefreshKey(prev => prev + 1);


   await fetchUpdatedDashboardTasks();
 };


 const handleNoTimetableDetected = useCallback(() => {
   setProjects(prevProjects =>
     prevProjects.map(p =>
       p.id === safeActiveProjectId ? { ...p, isTimetableLoaded: false } : p
     )
   );
 }, [safeActiveProjectId]);


 const calendarMappedAssignments: Assignment[] = [
   ...dbAssignments.map((task, idx) => ({
     id: Number(task.id),
     project_id: task.project_id || safeActiveProjectId,
     course_code: (task.project || task.course_code || 'GENERAL').toUpperCase(),
     course_name: task.course_name || 'Academic Course Outline',
     assessment_title: task.title || task.assessment_title || 'Unnamed Assignment Milestone',
     deadline_iso: task.planned_date || task.deadline_iso || '',
     priority: task.priority || 'Normal',
     sorting_score: task.sorting_score || (100 + idx),
     isDbRecord: true,
     rawTaskId: task.id
   }))
 ];


 return (
   <div className="flex h-screen w-screen bg-slate-50 font-sans overflow-hidden relative">
     <OnboardingModal
       isOpen={isStorageReady && activeProject ? !activeProject.isTimetableLoaded : false}
       projectName={activeProject?.name || ''}
       projectId={safeActiveProjectId}
       onClose={() => {
         setProjects(prev =>
           prev.map(p =>
             p.id === safeActiveProjectId ? { ...p, isTimetableLoaded: true } : p
           )
         );


         setTimetableRefreshKey(prev => prev + 1);
       }}
       onUploadSuccess={handleOnboardingSuccess}
     />


     <Sidebar
       projects={projects}
       activeProjectId={safeActiveProjectId}
       onSelectProject={handleSelectProject}
       onCreateNewProject={handleCreateNewProject}
       onDeleteProject={handleDeleteProject}
     />


     <div
       className={`flex-1 flex overflow-hidden transition-all duration-300 ${
         !activeProject?.isTimetableLoaded ? 'blur-sm pointer-events-none' : ''
       }`}
     >
       <main className="flex-1 p-6 overflow-hidden flex flex-col gap-4">
         <div className="w-full flex justify-between items-center py-1 px-2">
           <div className="w-32 invisible" aria-hidden="true" />


           <div className="bg-slate-200/80 p-1 rounded-xl flex gap-1 shadow-inner border border-slate-300/30">
             <button
               onClick={() => setCurrentView('timetable')}
               className={`px-5 py-2 rounded-lg text-xs font-bold transition-all duration-200 ${
                 currentView === 'timetable'
                   ? 'bg-white text-blue-600 shadow-md scale-[1.02]'
                   : 'text-slate-600 hover:text-slate-900 hover:bg-white/40'
               }`}
             >
               Timetable
             </button>


             <button
               onClick={() => setCurrentView('calendar')}
               className={`px-5 py-2 rounded-lg text-xs font-bold transition-all duration-200 ${
                 currentView === 'calendar'
                   ? 'bg-white text-blue-600 shadow-md scale-[1.02]'
                   : 'text-slate-600 hover:text-slate-900 hover:bg-white/40'
               }`}
             >
               Calendar
             </button>
           </div>


           <button
             onClick={handleExportTimetableImage}
             disabled={isExporting}
             className={`px-4 py-2 rounded-xl text-xs font-bold flex items-center gap-2 border shadow-sm transition-all duration-200 ${
               isExporting
                 ? 'bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed'
                 : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-50 hover:text-slate-900 active:scale-[0.98]'
             }`}
           >
             {isExporting ? (
               <>
                 <svg className="animate-spin h-3.5 w-3.5 text-slate-400" fill="none" viewBox="0 0 24 24">
                   <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                   <path
                     className="opacity-75"
                     fill="currentColor"
                     d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                   />
                 </svg>
                 Exporting...
               </>
             ) : (
               <>
                 <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                   <path
                     strokeLinecap="round"
                     strokeLinejoin="round"
                     d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                   />
                 </svg>
                 Export JPG
               </>
             )}
           </button>
         </div>


         <div className="flex-1 overflow-hidden">
           {currentView === 'timetable' ? (
             <TimetableGrid
               key={`${safeActiveProjectId}-${timetableRefreshKey}`}
               projectId={safeActiveProjectId}
               tasks={dbAssignments}
               courseBlocks={[]}
               onNoTimetableDetected={handleNoTimetableDetected}
             />
           ) : (
             <CalendarView
               projectId={safeActiveProjectId}
               assignments={calendarMappedAssignments}
               onDeleteAssignment={handleDeleteAssignmentLog}
             />
           )}
         </div>
       </main>


       <ChatContainer
         projectId={safeActiveProjectId}
         onTasksSaved={fetchUpdatedDashboardTasks}
       />
     </div>
   </div>
 );
}


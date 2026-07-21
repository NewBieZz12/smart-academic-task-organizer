'use client';
import React, { useState, useRef, useEffect } from 'react';


interface Message {
 id: string;
 sender: 'user' | 'ai';
 text: string;
 timestamp: string;
 isCourseBlockCard?: boolean;
}


interface ChatContainerProps {
 projectId?: string;
 onTasksSaved?: () => void;
 onCourseBlockCreated?: (newBlock: any) => void;
}


interface MilestoneBlock {
 milestone_id: number;
 project: string;
 title: string;
 planned_date: string;
 time_slot: string;
 priority: string;
 deadline_iso: string;
}


const API_BASE_URL = 'http://127.0.0.1:8000';


const normalizeProjectId = (projectId?: string) => {
 const cleaned = String(projectId || '').trim();
 return cleaned.length > 0 ? cleaned : 'project-1';
};


export default function ChatContainer({
 projectId = 'project-1',
 onTasksSaved,
 onCourseBlockCreated
}: ChatContainerProps) {
 const fileInputRef = useRef<HTMLInputElement>(null);
 const activeProjectId = normalizeProjectId(projectId);


 const [messages, setMessages] = useState<Message[]>([
   {
     id: 'm1',
     sender: 'ai',
     text: 'If you have a new course assignment brief or syllabus, just drop the PDF file right here or click the attachment icon below.',
     timestamp: 'Active Now'
   }
 ]);


 const [isDragOver, setIsDragOver] = useState(false);
 const [isExtracting, setIsExtracting] = useState(false);


 const [courseBlocks, setCourseBlocks] = useState<{ [msgId: string]: any }>({});
 const [assignmentSummaries, setAssignmentSummaries] = useState<{ [msgId: string]: any }>({});
 const [filePreviews, setFilePreviews] = useState<{ [msgId: string]: string }>({});
 const [savedTaskRegistry, setSavedTaskRegistry] = useState<{ [msgId: string]: 'idle' | 'saving' | 'saved' }>({});


 const [activeModalId, setActiveModalId] = useState<string | null>(null);


 const [isSchedulingStage, setIsSchedulingStage] = useState<boolean>(false);
 const [gaBlocksState, setGaBlocksState] = useState<MilestoneBlock[]>([]);


 const [showManualForm, setShowManualForm] = useState<boolean>(false);
 const [manualTitle, setManualTitle] = useState<string>('');
 const [manualDeadline, setManualDeadline] = useState<string>('');
 const [manualCourseCode, setManualCourseCode] = useState<string>('');


 const storageKey = (baseKey: string) => `${baseKey}_${activeProjectId}`;


 useEffect(() => {
   try {
     const cachedMessages = localStorage.getItem(storageKey('chat_history'));
     const cachedBlocks = localStorage.getItem(storageKey('chat_course_blocks'));
     const cachedSummaries = localStorage.getItem(storageKey('chat_assignment_summaries'));
     const cachedRegistry = localStorage.getItem(storageKey('chat_saved_task_registry'));


     if (cachedMessages) {
       setMessages(JSON.parse(cachedMessages));
     } else {
       setMessages([
         {
           id: 'm1',
           sender: 'ai',
           text: 'If you have a new course assignment brief or syllabus, just drop the PDF file right here or click the attachment icon below.',
           timestamp: 'Active Now'
         }
       ]);
     }


     setCourseBlocks(cachedBlocks ? JSON.parse(cachedBlocks) : {});
     setAssignmentSummaries(cachedSummaries ? JSON.parse(cachedSummaries) : {});
     setSavedTaskRegistry(cachedRegistry ? JSON.parse(cachedRegistry) : {});
     setFilePreviews({});
     setActiveModalId(null);
     setIsSchedulingStage(false);
     setGaBlocksState([]);
   } catch (err) {
     console.error('⚠️ Failed rehydrating browser chat history matrix:', err);
   }
   // eslint-disable-next-line react-hooks/exhaustive-deps
 }, [activeProjectId]);


 useEffect(() => {
   if (!activeModalId) {
     setIsSchedulingStage(false);
   }
 }, [activeModalId]);


 const updateMessagesAndPersist = (newMessages: Message[] | ((prev: Message[]) => Message[])) => {
   setMessages(prev => {
     const resolved = typeof newMessages === 'function' ? newMessages(prev) : newMessages;
     localStorage.setItem(storageKey('chat_history'), JSON.stringify(resolved));
     return resolved;
   });
 };


 const persistCourseBlocks = (next: { [msgId: string]: any }) => {
   localStorage.setItem(storageKey('chat_course_blocks'), JSON.stringify(next));
 };


 const persistAssignmentSummaries = (next: { [msgId: string]: any }) => {
   localStorage.setItem(storageKey('chat_assignment_summaries'), JSON.stringify(next));
 };


 const persistSavedTaskRegistry = (next: { [msgId: string]: 'idle' | 'saving' | 'saved' }) => {
   localStorage.setItem(storageKey('chat_saved_task_registry'), JSON.stringify(next));
 };


 const getClientTime = () => {
   return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
 };


 const normalizeTimeForCommit = (timeValue: string) => {
   const cleaned = String(timeValue || '12:00').trim();


   if (cleaned.length === 5) {
     return `${cleaned}:00`;
   }


   return cleaned;
 };


 const requestBalancedScheduleProposal = async (block: any): Promise<MilestoneBlock[]> => {
   const deadline =
     block.deadline_iso ||
     block.calendar_iso_date ||
     new Date().toISOString().split('T')[0];


   const res = await fetch(`${API_BASE_URL}/api/schedule/propose`, {
     method: 'POST',
     headers: { 'Content-Type': 'application/json' },
     body: JSON.stringify({
       project_id: activeProjectId,
       title: block.title || block.assignment_name,
       project: block.course_code || block.project || 'GENERAL',
       deadline_iso: deadline,
       priority: 'High'
     })
   });


   const data = await res.json().catch(() => ({}));


   if (!res.ok || !data.success || !Array.isArray(data.proposals)) {
     throw new Error(
       data.detail ||
       data.message ||
       'Schedule proposal failed. Please check backend scheduling API.'
     );
   }


   return data.proposals.map((item: any, index: number) => ({
     milestone_id: item.milestone_id || 1000 + index,
     project: item.project || block.course_code || block.project || 'GENERAL',
     title: item.title || `Milestone ${index + 1}`,
     planned_date: item.planned_date,
     time_slot: item.time_slot,
     priority: item.priority || 'High',
     deadline_iso: item.deadline_iso || deadline
   }));
 };


 const requestAssignmentSummary = async (file: File): Promise<string[]> => {
   const summaryFormData = new FormData();
   summaryFormData.append('file', file);


   const summaryResponse = await fetch(`${API_BASE_URL}/api/assignment/summarize`, {
     method: 'POST',
     body: summaryFormData
   });


   const summaryResult = await summaryResponse.json().catch(() => ({}));


   if (!summaryResponse.ok || !summaryResult.success) {
     throw new Error(
       summaryResult.detail ||
       summaryResult.message ||
       'Assignment summarizer API failed.'
     );
   }


   if (!Array.isArray(summaryResult.core_tasks)) {
     return ['No concrete target list array returned from summarizer.'];
   }


   const cleanedTasks = summaryResult.core_tasks
     .map((task: any) => String(task || '').trim())
     .filter((task: string) => task.length > 0);


   return cleanedTasks.length > 0
     ? cleanedTasks
     : ['No concrete target list array returned from summarizer.'];
 };


 const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
   if (e.target.files && e.target.files[0]) {
     handleFileUpload(e.target.files[0]);
   }
 };


 const handleCreateCustomAssignment = (e: React.FormEvent) => {
   e.preventDefault();
   if (!manualTitle || !manualDeadline) return;


   const targetMsgId = `course-block-${Date.now()}`;
   const cleanCourseCode = manualCourseCode.trim()
     ? manualCourseCode.trim().toUpperCase()
     : 'GENERAL';


   const newCourseBlock = {
     project_id: activeProjectId,
     course_code: cleanCourseCode,
     course_name: `Custom Task (${cleanCourseCode})`,
     assignment_name: manualTitle.trim(),
     submission_date: manualDeadline,
     calendar_iso_date: manualDeadline,
     title: manualTitle.trim(),
     project: cleanCourseCode,
     deadline_iso: manualDeadline
   };


   setCourseBlocks(prev => {
     const next = { ...prev, [targetMsgId]: newCourseBlock };
     persistCourseBlocks(next);
     return next;
   });


   setSavedTaskRegistry(prev => {
     const next = { ...prev, [targetMsgId]: 'idle' as const };
     persistSavedTaskRegistry(next);
     return next;
   });


   onCourseBlockCreated?.(newCourseBlock);


   setAssignmentSummaries(prev => {
     const next = {
       ...prev,
       [targetMsgId]: {
         core_tasks: [
           'User defined manual task item blueprint.',
           `Deliver complete work targets for: ${manualTitle.trim()}`
         ]
       }
     };
     persistAssignmentSummaries(next);
     return next;
   });


   updateMessagesAndPersist(prev => [
     ...prev,
     {
       id: `user-manual-${Date.now()}`,
       sender: 'user',
       text: ` Manually Added Task: "${manualTitle.trim()}" due on ${manualDeadline}`,
       timestamp: getClientTime()
     },
     {
       id: targetMsgId,
       sender: 'ai',
       text: 'Course Block Card Wrapper',
       timestamp: getClientTime(),
       isCourseBlockCard: true
     }
   ]);


   setManualTitle('');
   setManualDeadline('');
   setManualCourseCode('');
   setShowManualForm(false);
 };


 const handleFileUpload = async (file: File) => {
   if (!file) return;


   setIsExtracting(true);


   const targetMsgId = `course-block-${Date.now()}`;
   const objectUrl = URL.createObjectURL(file);
   setFilePreviews(prev => ({ ...prev, [targetMsgId]: objectUrl }));


   updateMessagesAndPersist(prev => [
     ...prev,
     {
       id: `user-file-${Date.now()}`,
       sender: 'user',
       text: `Uploaded file: ${file.name}`,
       timestamp: getClientTime()
     }
   ]);


   const parserFormData = new FormData();
   parserFormData.append('file', file);
   parserFormData.append('project_id', activeProjectId);


   try {
     // STEP 1: Assignment parser API
     // Endpoint: POST /api/assignment/upload
     const parserResponse = await fetch(`${API_BASE_URL}/api/assignment/upload`, {
       method: 'POST',
       body: parserFormData
     });


     if (!parserResponse.ok) {
       const errorData = await parserResponse.json().catch(() => ({}));
       throw new Error(errorData.detail || 'Boundary task extraction parsing failed.');
     }


     const parserResult = await parserResponse.json();


     // STEP 2: Assignment summarizer API
     // Endpoint: POST /api/assignment/summarize
     let resolvedCoreTasks: string[] = [];


     try {
       resolvedCoreTasks = await requestAssignmentSummary(file);
     } catch (summaryError: any) {
       console.error('⚠️ Assignment summarizer pipeline failure:', summaryError);


       resolvedCoreTasks = [
         summaryError?.message
           ? `Summarizer unavailable: ${summaryError.message}`
           : 'Summarizer unavailable. Please check whether Ollama qwen2.5:3b is running.'
       ];
     }


     const cleanedName = file.name.replace(/\.[^/.]+$/, '').replace(/[_-]/g, ' ');
     const fallbackIsoDate = new Date().toISOString().split('T')[0];


     const resolvedCourseCode =
       parserResult.course_code && parserResult.course_code !== 'Unable to detect'
         ? parserResult.course_code.toUpperCase()
         : cleanedName.split(' ')[0].toUpperCase();


     const newCourseBlock = {
       project_id: activeProjectId,
       course_code: resolvedCourseCode,
       course_name:
         parserResult.course_name && parserResult.course_name !== 'Unable to detect'
           ? parserResult.course_name
           : cleanedName,
       assignment_name:
         parserResult.assignment_name && parserResult.assignment_name !== 'Unable to detect'
           ? parserResult.assignment_name
           : 'Target Core Segment Tasks',
       submission_date: parserResult.submission_date || 'Not Explicitly Found',
       calendar_iso_date: parserResult.calendar_iso_date || fallbackIsoDate,
       title:
         parserResult.assignment_name && parserResult.assignment_name !== 'Unable to detect'
           ? parserResult.assignment_name
           : cleanedName,
       project: resolvedCourseCode,
       deadline_iso: parserResult.calendar_iso_date || fallbackIsoDate
     };


     setCourseBlocks(prev => {
       const next = { ...prev, [targetMsgId]: newCourseBlock };
       persistCourseBlocks(next);
       return next;
     });


     setSavedTaskRegistry(prev => {
       const next = { ...prev, [targetMsgId]: 'idle' as const };
       persistSavedTaskRegistry(next);
       return next;
     });


     onCourseBlockCreated?.(newCourseBlock);


     setAssignmentSummaries(prev => {
       const next = {
         ...prev,
         [targetMsgId]: {
           core_tasks: resolvedCoreTasks
         }
       };
       persistAssignmentSummaries(next);
       return next;
     });


     updateMessagesAndPersist(prev => [
       ...prev,
       {
         id: `ai-res-${Date.now()}`,
         sender: 'ai',
         text: ' Assignment parser and Qwen summarizer completed successfully. Review extracted details and task targets below.',
         timestamp: getClientTime()
       },
       {
         id: targetMsgId,
         sender: 'ai',
         text: 'Course Block Card Wrapper',
         timestamp: getClientTime(),
         isCourseBlockCard: true
       }
     ]);
   } catch (error: any) {
     console.error('❌ Component extraction pipeline failure:', error);
     updateMessagesAndPersist(prev => [
       ...prev,
       {
         id: `ai-err-${Date.now()}`,
         sender: 'ai',
         text: `❌ Evaluation breakdown window could not be isolated: ${error.message || '404/500 Router Misalignment'}`,
         timestamp: getClientTime()
       }
     ]);
   } finally {
     setIsExtracting(false);
   }
 };


 const handleInitializeSchedulingPreview = async (msgId: string) => {
   const block = courseBlocks[msgId];
   if (!block) return;


   try {
     const proposedMilestones = await requestBalancedScheduleProposal(block);


     setGaBlocksState(proposedMilestones);
     setIsSchedulingStage(true);
   } catch (err: any) {
     console.error('Failed calculating hybrid pipeline resource partitions:', err);


     alert(
       err.message ||
       'Could not generate a balanced schedule. Please check backend scheduling API.'
     );


     setIsSchedulingStage(false);
     setGaBlocksState([]);
   }
 };


 const handleSaveToDatabase = async (msgId: string) => {
   const block = courseBlocks[msgId];
   if (!block) return;


   if (!gaBlocksState || gaBlocksState.length === 0) {
     alert('No proposed schedule is available. Please run the Hybrid Scheduling Pipeline first.');
     return;
   }


   setSavedTaskRegistry(prev => {
     const next = { ...prev, [msgId]: 'saving' as const };
     persistSavedTaskRegistry(next);
     return next;
   });


   const formattedMilestones = gaBlocksState.map(m => ({
     title: m.title,
     project: m.project,
     planned_date: m.planned_date,
     planned_time: normalizeTimeForCommit(m.time_slot),
     deadline_iso: m.deadline_iso,
     priority: m.priority,
     sorting_score: 0
   }));


   try {
     const res = await fetch(`${API_BASE_URL}/api/schedule/commit`, {
       method: 'POST',
       headers: { 'Content-Type': 'application/json' },
       body: JSON.stringify({
         project_id: activeProjectId,
         course_code: block.course_code,
         assignment_name: block.assignment_name,
         deadline_iso: block.deadline_iso || new Date().toISOString().split('T')[0],
         milestones: formattedMilestones
       })
     });


     if (!res.ok) {
       const errorData = await res.json().catch(() => ({}));
       const errorMessage =
         errorData.detail ||
         errorData.message ||
         'Cascade database transaction failed.';


       const isDailyLimitIssue =
         res.status === 400 &&
         (
           errorMessage.toLowerCase().includes('daily workload') ||
           errorMessage.toLowerCase().includes('4 hours') ||
           errorMessage.toLowerCase().includes('limit exceeded') ||
           errorMessage.toLowerCase().includes('maximum allowed')
         );


       if (isDailyLimitIssue) {
         const refreshedProposal = await requestBalancedScheduleProposal(block);


         setGaBlocksState(refreshedProposal);
         setIsSchedulingStage(true);


         setSavedTaskRegistry(prev => {
           const next = { ...prev, [msgId]: 'idle' as const };
           persistSavedTaskRegistry(next);
           return next;
         });


         alert(
           'The selected date is already full with 4 hours. The GA has generated a new balanced schedule automatically. Please review and commit again.'
         );


         return;
       }


       throw new Error(errorMessage);
     }


     setSavedTaskRegistry(prev => {
       const next = { ...prev, [msgId]: 'saved' as const };
       persistSavedTaskRegistry(next);
       return next;
     });


     onTasksSaved?.();
     setIsSchedulingStage(false);
     setActiveModalId(null);
   } catch (err: any) {
     console.error('❌ Bulk database save processing failure:', err);


     setSavedTaskRegistry(prev => {
       const next = { ...prev, [msgId]: 'idle' as const };
       persistSavedTaskRegistry(next);
       return next;
     });


     alert(err.message || 'Could not persist milestone blocks down to SQLite database layer.');
   }
 };


 const clearChatHistory = () => {
   if (window.confirm('Are you sure you want to wipe the session workspace history?')) {
     localStorage.removeItem(storageKey('chat_history'));
     localStorage.removeItem(storageKey('chat_course_blocks'));
     localStorage.removeItem(storageKey('chat_assignment_summaries'));
     localStorage.removeItem(storageKey('chat_saved_task_registry'));


     setMessages([
       {
         id: 'm1',
         sender: 'ai',
         text: 'If you have a new brief, drop the file right here.',
         timestamp: 'Active Now'
       }
     ]);
     setCourseBlocks({});
     setAssignmentSummaries({});
     setSavedTaskRegistry({});
   }
 };


 return (
   <section
     onDragOver={(e) => {
       e.preventDefault();
       setIsDragOver(true);
     }}
     onDragLeave={() => setIsDragOver(false)}
     onDrop={(e) => {
       e.preventDefault();
       setIsDragOver(false);
       if (e.dataTransfer.files && e.dataTransfer.files[0]) {
         handleFileUpload(e.dataTransfer.files[0]);
       }
     }}
     className={`w-96 bg-white border-l border-slate-200 flex flex-col h-full relative ${
       isDragOver ? 'bg-blue-50/40 ring-2 ring-inset ring-blue-400' : ''
     }`}
   >
     <div className="p-4 border-b border-slate-100 bg-slate-50/50 flex items-center justify-between shrink-0">
       <div className="font-bold text-slate-700 text-sm flex items-center gap-2">
         <span className={`w-2 h-2 rounded-full ${isExtracting ? 'bg-amber-500 animate-ping' : 'bg-emerald-500'}`} />
         Chatbox
         
       </div>
       {messages.length > 1 && (
         <button
           onClick={clearChatHistory}
           className="text-[10px] text-slate-400 hover:text-red-500 font-semibold px-2 py-1 rounded-md hover:bg-red-50 transition-colors"
         >
           Clear Log
         </button>
       )}
     </div>


     <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50/30">
       {messages.map((msg) => {
         if (msg.isCourseBlockCard) {
           const blockData = courseBlocks[msg.id] || {};
           const saveStatus = savedTaskRegistry[msg.id] || 'idle';


           return (
             <div
               key={msg.id}
               onClick={() => setActiveModalId(msg.id)}
               className={`bg-gradient-to-br from-white to-slate-50 border-l-4 ${saveStatus === 'saved' ? 'border-emerald-500' : 'border-blue-500'} border-y border-r border-slate-200 shadow-sm rounded-r-xl rounded-l p-3.5 space-y-1.5 cursor-pointer hover:shadow-md hover:border-slate-300 transition-all max-w-[90%] relative group`}
             >
               <div className="flex items-center justify-between">
                 <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${saveStatus === 'saved' ? 'bg-emerald-50 text-emerald-700 border-emerald-100' : 'bg-blue-50 text-blue-700 border-blue-100'} border uppercase tracking-wide`}>
                   {blockData.course_code}
                 </span>
                 <span className="text-[10px] text-slate-400 font-medium group-hover:text-blue-600 transition-colors">
                   {saveStatus === 'saved' ? 'Saved Sync ✓' : 'Review Info '}
                 </span>
               </div>
               <h5 className="text-xs font-bold text-slate-800 line-clamp-1">{blockData.course_name}</h5>
               <p className="text-[11px] font-medium text-slate-600 truncate">{blockData.assignment_name}</p>
             </div>
           );
         }


         const isAi = msg.sender === 'ai';


         return (
           <div key={msg.id} className={`flex flex-col max-w-[85%] ${isAi ? 'mr-auto' : 'ml-auto items-end'}`}>
             <div className={`p-3 rounded-2xl text-xs leading-relaxed ${isAi ? 'bg-white border border-slate-200 text-slate-800' : 'bg-blue-600 text-white'}`}>
               {msg.text}
             </div>
             <span className="text-[9px] text-slate-400 mt-1 px-1">{msg.timestamp}</span>
           </div>
         );
       })}
     </div>


     {showManualForm && (
       <form
         onSubmit={handleCreateCustomAssignment}
         className="p-3 bg-slate-50 border-t border-slate-200 space-y-2.5 animate-slide-up shrink-0 shadow-inner"
       >
         <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wide flex items-center justify-between">
           <span> Custom Task</span>
           <button type="button" onClick={() => setShowManualForm(false)} className="text-slate-400 hover:text-slate-600 font-bold">✕</button>
         </div>


         <div className="grid grid-cols-3 gap-2">
           <div className="col-span-1">
             <label className="block text-[9px] font-bold text-slate-400 uppercase mb-0.5">Code</label>
             <input
               type="text"
               placeholder=""
               value={manualCourseCode}
               onChange={(e) => setManualCourseCode(e.target.value)}
               className="w-full text-xs p-1.5 border border-slate-200 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 uppercase text-slate-700 bg-white"
             />
           </div>
           <div className="col-span-2">
             <label className="block text-[9px] font-bold text-slate-400 uppercase mb-0.5">Task Title</label>
             <input
               type="text"
               required
               placeholder=""
               value={manualTitle}
               onChange={(e) => setManualTitle(e.target.value)}
               className="w-full text-xs p-1.5 border border-slate-200 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 text-slate-700 bg-white"
             />
           </div>
         </div>


         <div className="flex gap-2 items-center">
           <div className="flex-1">
             <label className="block text-[9px] font-bold text-slate-400 uppercase mb-0.5">Deadline</label>
             <input
               type="date"
               required
               value={manualDeadline}
               onChange={(e) => setManualDeadline(e.target.value)}
               className="w-full text-xs p-1.5 border border-slate-200 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 text-slate-700 bg-white"
             />
           </div>
           <button
             type="submit"
             className="mt-4 px-4 py-1.5 bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs rounded-md shadow-sm transition-colors h-[32px]"
           >
             Add Task
           </button>
         </div>
       </form>
     )}


     <div className="p-3 bg-white border-t border-slate-100 flex flex-col gap-2 shrink-0">
       <input type="file" ref={fileInputRef} onChange={handleFileChange} accept=".pdf,.txt" className="hidden" />
       <div className="flex items-center gap-2">
         <button
           type="button"
           onClick={() => fileInputRef.current?.click()}
           disabled={isExtracting}
           className="flex items-center justify-center p-2 text-slate-500 hover:text-blue-600 hover:bg-blue-50 rounded-xl transition-all border border-slate-200 disabled:opacity-50"
           title="Upload Brief PDF"
         >
           📎
         </button>


         <button
           type="button"
           onClick={() => setShowManualForm(!showManualForm)}
           className={`flex items-center justify-center p-2 rounded-xl transition-all border text-xs font-bold gap-1 ${showManualForm ? 'bg-amber-50 text-amber-600 border-amber-200' : 'bg-slate-50 text-slate-600 hover:bg-slate-100 border-slate-200'}`}
           title="Add Task Manually"
         >
           <span>＋ Custom Task</span>
         </button>


         <div className="flex-1 text-right text-[11px] text-slate-400 italic py-1 truncate">
           {isExtracting ? 'Running task boundary isolation...' : 'Drop file here'}
         </div>
       </div>
     </div>


     {activeModalId && (() => {
       const block = courseBlocks[activeModalId] || {};
       const summary = assignmentSummaries[activeModalId] || { core_tasks: [] };
       const fileUrl = filePreviews[activeModalId] || '';
       const saveStatus = savedTaskRegistry[activeModalId] || 'idle';


       return (
         <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-6">
           <div className="bg-white w-full max-w-5xl h-[85vh] rounded-2xl shadow-xl border border-slate-200 flex flex-col overflow-hidden">


             <div className="p-4 border-b border-slate-100 bg-slate-50/50 flex items-center justify-between">
               <div>
                 <div className="flex items-center gap-2">
                   <span className="text-xs font-bold px-2 py-0.5 rounded bg-blue-100 text-blue-800 uppercase tracking-wide">{block.course_code}</span>
                   <h4 className="text-sm font-bold text-slate-800">{block.course_name}</h4>
                 </div>
                 <p className="text-xs text-slate-500 mt-0.5">{block.assignment_name}</p>
               </div>


               <div className="flex items-center gap-2">
                 {isSchedulingStage && (
                   <button
                     onClick={() => handleSaveToDatabase(activeModalId)}
                     disabled={saveStatus === 'saving'}
                     className="text-xs font-bold px-4 py-2 rounded-xl border transition-all shadow-sm bg-emerald-600 hover:bg-emerald-700 text-white border-emerald-700"
                   >
                     {saveStatus === 'saving' ? 'Saving Timeline Changes...' : 'Confirm Schedule ✓'}
                   </button>
                 )}
                 <button
                   onClick={() => {
                     setActiveModalId(null);
                     setIsSchedulingStage(false);
                   }}
                   className="text-slate-500 hover:text-slate-700 font-bold text-xs p-2 px-3.5 rounded-xl bg-slate-100 border border-slate-200"
                 >
                   Close Window ✕
                 </button>
               </div>
             </div>


             <div className="flex-1 flex overflow-hidden">
               <div className="w-1/2 p-5 overflow-y-auto space-y-5 border-r border-slate-100">


                 <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 space-y-3 shadow-sm">
                   <h5 className="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1">
                      Extracted Course Details
                   </h5>


                   <div className="grid grid-cols-2 gap-3 text-xs">
                     <div className="col-span-2">
                       <span className="block text-[9px] font-bold text-slate-400 uppercase tracking-wide mb-0.5">Course Identification Name</span>
                       <div className="font-semibold text-slate-800 bg-white border border-slate-200 px-2.5 py-1.5 rounded-lg truncate shadow-sm">
                         {block.course_name || 'Academic Course Assignment'}
                       </div>
                     </div>


                     <div>
                       <span className="block text-[9px] font-bold text-slate-400 uppercase tracking-wide mb-0.5">Assessment Task Title</span>
                       <div className="font-semibold text-slate-700 bg-white border border-slate-200 px-2.5 py-1.5 rounded-lg truncate shadow-sm">
                         {block.assignment_name || 'Target Tasks'}
                       </div>
                     </div>


                     <div>
                       <span className="block text-[9px] font-bold text-slate-400 uppercase tracking-wide mb-0.5">Extracted Submission Deadline</span>
                       <div className="font-semibold text-slate-700 bg-white border border-slate-200 px-2.5 py-1.5 rounded-lg shadow-sm flex items-center gap-1.5">
                          {block.submission_date || 'Not Set'}
                       </div>
                     </div>
                   </div>
                 </div>


                 <hr className="border-slate-100" />


                 {!isSchedulingStage ? (
                   <div className="space-y-4">
                     <h5 className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Optimization Schedule </h5>
                     <button
                       onClick={() => handleInitializeSchedulingPreview(activeModalId)}
                       className="w-full p-4 border border-blue-200 rounded-xl bg-gradient-to-r from-blue-50 to-indigo-50 hover:from-blue-100 hover:to-indigo-100 text-left transition-all group flex flex-col gap-1"
                     >
                       <div className="font-bold text-xs text-blue-900 flex items-center gap-1.5">
                          Run Hybrid Scheduling
                       </div>
                       <div className="text-[11px] text-blue-700/80 leading-normal">
                         Calculates optimal scheduling using a Greedy, GA and Resource Leveling.
                       </div>
                     </button>
                   </div>
                 ) : (
                   <div className="space-y-4">
                     <div className="p-3.5 border rounded-xl from-blue-50 to-indigo-50/50 border-blue-100 bg-gradient-to-r">
                       <h5 className="text-xs font-bold flex items-center gap-1.5 uppercase tracking-wider text-blue-800">
                          DATE ADJUSTMENT
                       </h5>
                       <p className="text-[11px] text-slate-500 mt-1 leading-relaxed">
                         It will automatic adjust schedule based on Greedy,GA and Resource Leveling.
                       </p>
                     </div>


                     <div className="space-y-4 max-h-[35vh] overflow-y-auto pr-1">
                       {gaBlocksState.map((item, index) => (
                         <div key={item.milestone_id || index} className="p-3.5 bg-slate-50/70 rounded-xl border border-slate-200/70 space-y-2.5 relative">
                           <div className="absolute top-2.5 right-2.5 text-[9px] font-extrabold px-2 py-0.5 bg-slate-200 text-slate-600 rounded uppercase tracking-wider">
                             Phase {index + 1}
                           </div>
                           <div>
                             <label className="block text-[9px] font-bold text-slate-400 uppercase tracking-wide mb-1">Phase Title</label>
                             <input
                               type="text"
                               className="w-full bg-white border border-slate-200 rounded-lg p-2 text-xs font-semibold text-slate-700"
                               value={item.title}
                               onChange={(e) => {
                                 const updated = [...gaBlocksState];
                                 updated[index].title = e.target.value;
                                 setGaBlocksState(updated);
                               }}
                             />
                           </div>
                           <div className="grid grid-cols-2 gap-3">
                             <div>
                               <label className="block text-[9px] font-bold text-slate-400 uppercase tracking-wide mb-1">Planned Date</label>
                               <input
                                 type="date"
                                 className="w-full bg-white border border-slate-200 rounded-lg p-2 text-xs text-slate-700"
                                 value={item.planned_date}
                                 onChange={(e) => {
                                   const updated = [...gaBlocksState];
                                   updated[index].planned_date = e.target.value;
                                   setGaBlocksState(updated);
                                 }}
                               />
                             </div>
                             <div>
                               <label className="block text-[9px] font-bold text-slate-400 uppercase tracking-wide mb-1">Allocated Time Block</label>
                               <input
                                 type="time"
                                 className="w-full bg-white border border-slate-200 rounded-lg p-2 text-xs text-slate-700"
                                 value={item.time_slot.slice(0, 5)}
                                 onChange={(e) => {
                                   const updated = [...gaBlocksState];
                                   updated[index].time_slot = e.target.value;
                                   setGaBlocksState(updated);
                                 }}
                               />
                             </div>
                           </div>
                         </div>
                       ))}
                     </div>


                     <button type="button" onClick={() => setIsSchedulingStage(false)} className="text-[11px] text-blue-500 hover:text-blue-700 font-semibold pt-1">
                       &larr; Re-calculate schedule
                     </button>
                   </div>
                 )}


                 <hr className="border-slate-100" />


                 <div>
                   <h5 className="text-xs font-bold text-slate-800 uppercase tracking-wide mb-3"> Goal and Target</h5>
                   <div className="bg-slate-50 border border-slate-200/60 p-4 rounded-xl">
                     {summary.core_tasks && summary.core_tasks.length > 0 ? (
                       <ul className="list-disc pl-4 space-y-2 text-[11px] text-slate-700 font-medium">
                         {summary.core_tasks.map((sentence: string, sIdx: number) => (
                           <li key={sIdx} className="bg-white p-2 rounded border border-slate-100 shadow-sm list-none flex items-center gap-2">
                             <span className="w-1.5 h-1.5 bg-blue-500 rounded-full shrink-0" />
                             {sentence}
                           </li>
                         ))}
                       </ul>
                     ) : (
                       <p className="text-[11px] italic text-slate-400">Parsing targeted text segment...</p>
                     )}
                   </div>
                 </div>
               </div>


               <div className="w-1/2 bg-slate-100 flex flex-col relative">
                 {fileUrl ? (
                   <iframe src={`${fileUrl}#toolbar=0&navpanes=0`} className="w-full h-full border-0" title="Source Brief" />
                 ) : (
                   <div className="m-auto text-xs text-slate-400 italic">No document visualization active (Manual Entry Target).</div>
                 )}
               </div>
             </div>


           </div>
         </div>
       );
     })()}
   </section>
 );
}




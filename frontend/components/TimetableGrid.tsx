// TimetableGrid.tsx
'use client';


import React, { useEffect, useState } from 'react';


interface Task {
 title: string;
 project: string;
 deadline_iso: string;
 priority: string;
 sorting_score: number;
}


interface TimetableGridProps {
 projectId?: string;
 tasks?: Task[];
 courseBlocks?: any[];
 onTimeSlotSelect?: (selection: { day: string; start_time: string; end_time: string }) => void;
 onNoTimetableDetected?: () => void;
 onCourseBlockSelect?: (blockId: string) => void;
}


export default function TimetableGrid({
 projectId = 'project-1',
 tasks = [],
 courseBlocks = [],
 onTimeSlotSelect,
 onNoTimetableDetected,
 onCourseBlockSelect
}: TimetableGridProps) {
 const [currentPivotDate, setCurrentPivotDate] = useState<Date>(new Date());
 const [weeklyData, setWeeklyData] = useState<any[]>([]);
 const [timetableBlocks, setTimetableBlocks] = useState<any[]>([]);
 const [weekBounds, setWeekBounds] = useState({ start: '', end: '' });
 const [loading, setLoading] = useState<boolean>(false);


 const [isDragging, setIsDragging] = useState(false);
 const [dragStart, setDragStart] = useState<{ dayIdx: number; timeIdx: number } | null>(null);
 const [dragEnd, setDragEnd] = useState<{ dayIdx: number; timeIdx: number } | null>(null);


 const days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];


 const timeSlots = [
   '08:00', '09:00', '10:00', '11:00', '12:00', '13:00', '14:00',
   '15:00', '16:00', '17:00', '18:00', '19:00', '20:00', '21:00', '22:00'
 ];


 useEffect(() => {
   let isMounted = true;


   const fetchTimetableData = async () => {
     try {
       const safeProjectId = (projectId || 'project-1').trim();


       const res = await fetch(
         `http://127.0.0.1:8000/api/timetable-data?project_id=${encodeURIComponent(safeProjectId)}`
       );


       if (!res.ok) {
         throw new Error(`Failed to fetch timetable data. HTTP ${res.status}`);
       }


       const payload = await res.json();


       if (isMounted && payload.success) {
         const rows = Array.isArray(payload.data) ? payload.data : [];
         setTimetableBlocks(rows);


         if (rows.length === 0 && onNoTimetableDetected) {
           onNoTimetableDetected();
         }
       }
     } catch (err) {
       console.error('❌ Failed to fetch real timetable data:', err);


       if (isMounted) {
         setTimetableBlocks([]);
       }
     }
   };


   fetchTimetableData();


   return () => {
     isMounted = false;
   };
 }, [projectId, onNoTimetableDetected]);


 useEffect(() => {
   let isMounted = true;


   const fetchWeeklyCalendarGrid = async () => {
     setLoading(true);


     try {
       const targetDateStr = currentPivotDate.toISOString().split('T')[0];
       const safeProjectId = (projectId || 'project-1').trim();


       const apiUrl =
         `http://127.0.0.1:8000/api/schedule/weekly-view?target_date=${encodeURIComponent(targetDateStr)}&project_id=${encodeURIComponent(safeProjectId)}`;


       const res = await fetch(apiUrl);


       if (!res.ok) {
         let backendMessage = `HTTP ${res.status}`;


         try {
           const errorPayload = await res.json();
           backendMessage = errorPayload?.detail || JSON.stringify(errorPayload);
         } catch {
           backendMessage = await res.text();
         }


         throw new Error(`Network response breakdown on backend calendar sync: ${backendMessage}`);
       }


       const jsonResult = await res.json();


       if (isMounted && jsonResult.success) {
         setWeeklyData(jsonResult.data.events || []);
         setWeekBounds({
           start: jsonResult.data.week_start,
           end: jsonResult.data.week_end
         });
       }
     } catch (err) {
       console.error('❌ Failed linking frontend calendar to API route payload:', err);


       if (isMounted) {
         setWeeklyData([]);
       }
     } finally {
       if (isMounted) setLoading(false);
     }
   };


   fetchWeeklyCalendarGrid();


   return () => {
     isMounted = false;
   };
 }, [currentPivotDate, projectId]);


 const stepWeek = (direction: 'prev' | 'next') => {
   const nextDate = new Date(currentPivotDate);
   nextDate.setDate(currentPivotDate.getDate() + (direction === 'next' ? 7 : -7));
   setCurrentPivotDate(nextDate);
 };


 const jumpToToday = () => {
   setCurrentPivotDate(new Date());
 };


 const handleMouseDown = (dayIdx: number, timeIdx: number) => {
   setIsDragging(true);
   setDragStart({ dayIdx, timeIdx });
   setDragEnd({ dayIdx, timeIdx });
 };


 const handleMouseEnter = (dayIdx: number, timeIdx: number) => {
   if (!isDragging || !dragStart) return;


   if (dayIdx === dragStart.dayIdx) {
     setDragEnd({ dayIdx, timeIdx });
   }
 };


 const handleMouseUp = () => {
   if (!isDragging || !dragStart || !dragEnd) return;


   setIsDragging(false);


   const startRow = Math.min(dragStart.timeIdx, dragEnd.timeIdx);
   const endRow = Math.max(dragStart.timeIdx, dragEnd.timeIdx);


   const selectedDay = days[dragStart.dayIdx];
   const startTime = timeSlots[startRow];
   const endTime = endRow + 1 < timeSlots.length ? timeSlots[endRow + 1] : '23:00';


   console.log(`🎯 Drag Selection Complete: ${selectedDay} (${startTime} -> ${endTime})`);


   if (onTimeSlotSelect) {
     onTimeSlotSelect({
       day: selectedDay,
       start_time: startTime,
       end_time: endTime
     });
   }


   setDragStart(null);
   setDragEnd(null);
 };


 const isCellSelected = (dayIdx: number, timeIdx: number) => {
   if (!dragStart || !dragEnd) return false;
   if (dayIdx !== dragStart.dayIdx) return false;


   const minRow = Math.min(dragStart.timeIdx, dragEnd.timeIdx);
   const maxRow = Math.max(dragStart.timeIdx, dragEnd.timeIdx);


   return timeIdx >= minRow && timeIdx <= maxRow;
 };


 const getDayNameFromIso = (dateString: string): string => {
   if (!dateString) return '';


   try {
     const dateObj = new Date(dateString);


     if (!isNaN(dateObj.getTime())) {
       return dateObj.toLocaleDateString('en-US', { weekday: 'long' });
     }


     const normalized = String(dateString).trim().toLowerCase();


     if (normalized.includes('mon')) return 'Monday';
     if (normalized.includes('tue')) return 'Tuesday';
     if (normalized.includes('wed')) return 'Wednesday';
     if (normalized.includes('thu')) return 'Thursday';
     if (normalized.includes('fri')) return 'Friday';
     if (normalized.includes('sat')) return 'Saturday';
     if (normalized.includes('sun')) return 'Sunday';


     return '';
   } catch {
     return '';
   }
 };


 const normalizeDayName = (value: any): string => {
   if (!value) return '';


   const raw = String(value).trim();


   const exact = days.find(day => day.toLowerCase() === raw.toLowerCase());
   if (exact) return exact;


   return getDayNameFromIso(raw);
 };


 const getEventStartTime = (event: any): string => {
   if (event.planned_time) return String(event.planned_time).substring(0, 5);
   if (event.time_slot) return String(event.time_slot).substring(0, 5);
   if (event.start_iso) return String(event.start_iso).substring(11, 16);
   if (event.start_time) return String(event.start_time).substring(0, 5);


   if (event.time && String(event.time).includes('-')) {
     return String(event.time).split('-')[0].trim().substring(0, 5);
   }


   return '';
 };


 const getEventEndTime = (event: any): string => {
   if (event.end_time) return String(event.end_time).substring(0, 5);
   if (event.end_iso) return String(event.end_iso).substring(11, 16);


   if (event.time && String(event.time).includes('-')) {
     return String(event.time).split('-')[1].trim().substring(0, 5);
   }


   const startTime = getEventStartTime(event);
   if (!startTime) return '';


   const [hour, minute] = startTime.split(':').map(Number);


   if (Number.isNaN(hour) || Number.isNaN(minute)) return '';


   return `${String(hour + 2).padStart(2, '0')}:${String(minute).padStart(2, '0')}`;
 };


 const calculateRowSpan = (startTime: string, endTime: string) => {
   const startTimeIndex = timeSlots.indexOf(startTime);
   const endTimeIndex = timeSlots.indexOf(endTime);


   if (startTimeIndex === -1) return 1;


   if (endTimeIndex !== -1 && endTimeIndex > startTimeIndex) {
     return endTimeIndex - startTimeIndex;
   }


   return 1;
 };


 const getCourseBlockDisplay = (block: any) => {
   const courseCode =
     block.course_code ||
     block.courseCode ||
     block.code ||
     block.project ||
     block.subject_code ||
     'UNKNOWN';


   const courseName =
     block.course_name ||
     block.courseName ||
     block.name ||
     block.subject_name ||
     block.title ||
     'Unnamed Course';


   const venueRoom =
     block.course_venue ||
     block.venue_room ||
     block.venue ||
     block.room ||
     block.location ||
     'No venue';


   const rawStartTime =
     block.start_time ||
     block.startTime ||
     getEventStartTime(block);


   const rawEndTime =
     block.end_time ||
     block.endTime ||
     getEventEndTime(block);


   const startTime = rawStartTime ? String(rawStartTime).substring(0, 5) : '';
   const endTime = rawEndTime ? String(rawEndTime).substring(0, 5) : '';


   const time =
     block.time && String(block.time).includes('-')
       ? String(block.time)
       : startTime && endTime
         ? `${startTime} - ${endTime}`
         : block.time || 'No time';


   const day =
     normalizeDayName(
       block.class_day ||
       block.day ||
       block.weekday ||
       block.date ||
       block.class_date ||
       block.planned_date
     );


   const week =
     block.week ||
     block.academic_week ||
     block.class_week ||
     block.weeks ||
     'Not specified';


   return {
     courseCode: String(courseCode).toUpperCase(),
     courseName: String(courseName),
     venueRoom: String(venueRoom),
     startTime,
     endTime,
     time,
     day,
     week
   };
 };


 const mergedTimetableBlocks = [...timetableBlocks, ...courseBlocks];


 const visibleSchedulerEvents = weeklyData.filter((event: any) => {
   const isClassEvent =
     Boolean(event.is_fixed_class) ||
     event.type === 'CLASS' ||
     event.type === 'class';


   return !isClassEvent;
 });


 const hasAnyEvent = mergedTimetableBlocks.length > 0 || visibleSchedulerEvents.length > 0;


 return (
   <div
     className="w-full h-full bg-white rounded-2xl shadow-sm border border-slate-200 flex flex-col overflow-hidden select-none"
     onMouseLeave={() => setIsDragging(false)}
   >
     <div className="p-4 border-b border-slate-100 bg-slate-50/50 flex flex-col sm:flex-row gap-3 justify-between items-start sm:items-center shrink-0">
       <div className="flex flex-col">
         <h2 className="font-bold text-slate-800 text-base flex items-center gap-2">
           Timetable
           {loading && (
             <span className="text-xs font-normal text-indigo-500 animate-pulse">
               (Updating Grid...)
             </span>
           )}
         </h2>


         <p className="text-[11px] text-slate-400">
           {weekBounds.start
             ? `Timeline (Week): ${weekBounds.start} to ${weekBounds.end}`
             : 'Calculating dynamic date bounds...'}
         </p>
       </div>


       <div className="flex items-center gap-1.5 bg-white p-1 rounded-lg border border-slate-200 shadow-sm self-stretch sm:self-auto justify-between">
         <button
           onClick={() => stepWeek('prev')}
           className="px-2.5 py-1 text-xs font-semibold text-slate-600 hover:bg-slate-50 rounded-md transition-colors"
         >
           ◀ Prev
         </button>


         <button
           onClick={jumpToToday}
           className="px-3 py-1 text-xs font-bold text-indigo-600 bg-indigo-50 hover:bg-indigo-100/70 rounded-md transition-colors"
         >
           Today
         </button>


         <button
           onClick={() => stepWeek('next')}
           className="px-2.5 py-1 text-xs font-semibold text-slate-600 hover:bg-slate-50 rounded-md transition-colors"
         >
           Next ▶
         </button>
       </div>
     </div>


     <div className="flex-1 overflow-auto p-6 bg-white max-h-[calc(100vh-180px)]">
       {!hasAnyEvent ? (
         <div className="w-full py-24 border border-dashed border-slate-200 rounded-xl flex flex-col items-center justify-center text-center p-6 bg-slate-50/30">
           <h3 className="font-bold text-slate-700 text-sm">No Timetable Data Found</h3>
           <p className="text-xs text-slate-400 max-w-xs mt-1">
             Upload a timetable image first.
           </p>
         </div>
       ) : (
         <div className="min-w-[1400px] grid grid-cols-[110px_1fr_1fr_1fr_1fr_1fr_1fr_1fr] relative border border-slate-200 rounded-xl bg-white overflow-hidden">
           <div
             style={{ gridColumnStart: 1, gridRowStart: 1 }}
             className="bg-slate-100 text-center text-xs font-bold text-slate-600 sticky top-0 left-0 z-40 flex items-center justify-center border-b border-r border-slate-200 h-12"
           >
             Time Duration
           </div>


           {days.map((day, dayIdx) => (
             <div
               key={day}
               style={{ gridColumnStart: dayIdx + 2, gridRowStart: 1 }}
               className="bg-slate-50 text-center text-xs font-bold text-slate-700 sticky top-0 z-20 border-b border-r last:border-r-0 border-slate-200 flex items-center justify-center h-12 shadow-sm"
             >
               {day}
             </div>
           ))}


           {timeSlots.map((time, timeIdx) => {
             const gridRowStart = timeIdx + 2;
             const currentHour = parseInt(time.split(':')[0], 10);
             const nextHourStr = `${String(currentHour + 1).padStart(2, '0')}:00`;
             const formattedSpanLabel = `${time} - ${nextHourStr}`;


             return (
               <React.Fragment key={time}>
                 <div
                   style={{ gridColumnStart: 1, gridRowStart }}
                   className="bg-slate-50 p-1.5 text-center text-[10px] font-bold text-slate-500 min-h-[5rem] h-full flex items-center justify-center sticky left-0 z-30 border-b border-r border-slate-200 bg-gradient-to-r from-slate-50 to-slate-100/70"
                 >
                   <span>{formattedSpanLabel}</span>
                 </div>


                 {days.map((day, dayIdx) => {
                   const selected = isCellSelected(dayIdx, timeIdx);


                   return (
                     <div
                       key={`${day}-${time}`}
                       style={{ gridColumnStart: dayIdx + 2, gridRowStart }}
                       onMouseDown={() => handleMouseDown(dayIdx, timeIdx)}
                       onMouseEnter={() => handleMouseEnter(dayIdx, timeIdx)}
                       onMouseUp={handleMouseUp}
                       className={`min-h-[5rem] h-full border-b border-r last:border-r-0 border-slate-100 cursor-crosshair transition-colors duration-75 relative ${
                         selected ? 'bg-indigo-50/80 border-indigo-200' : 'bg-white hover:bg-slate-50/40'
                       }`}
                     >
                       {selected && dragStart && dragStart.timeIdx === timeIdx && (
                         <div className="absolute top-1 left-1 right-1 bg-indigo-600 text-white font-semibold rounded text-[9px] px-1.5 py-0.5 shadow-sm pointer-events-none z-30 truncate animate-pulse">
                           ⚡ Release to form data...
                         </div>
                       )}
                     </div>
                   );
                 })}
               </React.Fragment>
             );
           })}


           {/* REAL TIMETABLE BLOCKS FROM /api/timetable-data */}
           {mergedTimetableBlocks.map((block: any, idx: number) => {
             const display = getCourseBlockDisplay(block);


             const dayIndex = days.indexOf(display.day);
             const startTimeIndex = timeSlots.indexOf(display.startTime);


             if (dayIndex === -1 || startTimeIndex === -1) {
               console.warn('⚠️ Timetable block skipped because day/time is missing or invalid:', block);
               return null;
             }


             const rowSpan = calculateRowSpan(display.startTime, display.endTime);
             const targetBlockId = String(block.id || block.block_id || `course-block-${idx}`);


             return (
               <div
                 key={`timetable-block-${targetBlockId}-${idx}`}
                 onClick={(e) => {
                   e.stopPropagation();
                   onCourseBlockSelect?.(targetBlockId);
                 }}
                 onMouseDown={(e) => e.stopPropagation()}
                 style={{
                   gridColumnStart: dayIndex + 2,
                   gridRowStart: startTimeIndex + 2,
                   gridRowEnd: `span ${Math.max(rowSpan, 1)}`
                 }}
                 className="m-1 p-2.5 rounded-lg border bg-gradient-to-br from-blue-50 to-indigo-50 border-blue-200 text-blue-900 shadow-sm flex flex-col justify-between overflow-hidden z-20 pointer-events-auto cursor-pointer hover:shadow-md hover:border-blue-300 active:scale-[0.98] transition-all"
                 title={`${display.courseCode} ${display.courseName} ${display.venueRoom} ${display.time}`}
               >
                 <div className="w-full">
                   <div className="flex items-center justify-between gap-1 mb-1">
                     <span className="text-[8px] font-bold uppercase tracking-wider px-1.5 py-0.5 border rounded inline-block bg-white/90 text-blue-700 border-blue-100">
                       CLASS
                     </span>


                     <span className="text-[8px] font-bold tracking-tight px-1 rounded bg-indigo-100 text-indigo-700">
                       {display.courseCode}
                     </span>
                   </div>


                   <h4 className="text-[11px] font-bold text-slate-800 leading-snug line-clamp-2">
                     {display.courseName}
                   </h4>
                 </div>


                 <div className="text-[10px] space-y-0.5 opacity-95 font-medium border-t border-black/5 pt-1 mt-1.5 w-full text-slate-500">
                   <p className="text-[9px] text-slate-500 truncate">
                     📍 {display.venueRoom}
                   </p>


                   <p>
                     ⏰ {display.time} (class)
                   </p>


                   {display.week && display.week !== 'Not specified' && (
                     <p className="text-[9px] text-slate-400 truncate">
                       🗓️ Week: {display.week}
                     </p>
                   )}
                 </div>
               </div>
             );
           })}


           {/* SCHEDULER TASK BLOCKS ONLY */}
           {visibleSchedulerEvents.map((event: any, idx: number) => {
             const dateDayName = getDayNameFromIso(event.planned_date);
             const dayIndex = days.indexOf(dateDayName);


             const rawTime = getEventStartTime(event);
             const endTime = getEventEndTime(event);
             const startTimeIndex = timeSlots.indexOf(rawTime);


             if (dayIndex === -1 || startTimeIndex === -1) return null;


             const gridRowStart = startTimeIndex + 2;
             const rowSpan = calculateRowSpan(rawTime, endTime);


             const courseCode =
               event.course_code ||
               event.project ||
               event.code ||
               'GENERAL';


             const taskTitle =
               event.title ||
               event.task_title ||
               event.assessment_title ||
               'Unnamed Task';


             return (
               <div
                 key={`scheduler-task-${event.id || idx}-${event.planned_date}-${startTimeIndex}-${idx}`}
                 style={{
                   gridColumnStart: dayIndex + 2,
                   gridRowStart,
                   gridRowEnd: `span ${Math.max(rowSpan, 1)}`
                 }}
                 className="m-1 p-2.5 rounded-lg border shadow-sm flex flex-col justify-between overflow-hidden z-10 pointer-events-auto transition-all hover:shadow-md bg-gradient-to-br from-emerald-50 to-teal-50 border-emerald-200 text-emerald-900 hover:border-emerald-300"
               >
                 <div className="w-full">
                   <div className="flex items-center justify-between gap-1 mb-1">
                     <span className="text-[8px] font-bold uppercase tracking-wider px-1.5 py-0.5 border rounded inline-block bg-white/90 text-emerald-700 border-emerald-100">
                       TASK
                     </span>


                     <span className="text-[8px] font-bold tracking-tight px-1 rounded bg-emerald-100 text-emerald-700">
                       {courseCode}
                     </span>
                   </div>


                   <h4 className="text-[11px] font-bold text-slate-800 leading-snug line-clamp-2">
                     {taskTitle}
                   </h4>
                 </div>


                 <div className="text-[10px] space-y-0.5 opacity-95 font-medium border-t border-black/5 pt-1 mt-1.5 w-full text-slate-500">
                   <p>
                     ⏰ {rawTime}{endTime ? ` - ${endTime}` : ''} (task)
                   </p>


                   {event.deadline_iso && (
                     <p className="text-[9px] text-red-500 font-semibold truncate">
                       🎯 Deadline: {String(event.deadline_iso).split('T')[0]}
                     </p>
                   )}
                 </div>
               </div>
             );
           })}
         </div>
       )}
     </div>
   </div>
 );
}


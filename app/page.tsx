import trackerData from '../public/data/tracker.json';
import RecallDashboard from './recall-dashboard';

export default function Home() {
  return <RecallDashboard initialData={trackerData} />;
}

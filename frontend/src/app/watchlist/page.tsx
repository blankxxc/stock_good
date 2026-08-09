import { WatchlistBoard } from '../../components/WatchlistBoard';

export const metadata = {
  title: '我的自选 | Obsidian Alpha',
  description: '当前账号私有的自选股票列表。',
};

export default function Page() {
  return <WatchlistBoard />;
}

import { StrategyLab } from '../../components/StrategyLab';

export const metadata = { title: '策略实验 · 历史回溯', description: '设置历史区间和选股参数，对比策略表现并逐日回放持仓与成交。' };

export default function Page() {
  return <StrategyLab />;
}

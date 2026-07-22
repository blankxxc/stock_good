import type { Metadata } from 'next';

import { ModelsComparisonDashboard } from '../../components/ModelsComparisonDashboard';

export const metadata: Metadata = {
  title: '模型对比 | Stock Good',
  description: '比较股票研究模型的预测质量、收益风险与运行效率。',
};

export default function Page() {
  return <ModelsComparisonDashboard />;
}

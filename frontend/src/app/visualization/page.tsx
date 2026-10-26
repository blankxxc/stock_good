import { VisualizationWorkbench } from '../../components/VisualizationWorkbench';

export const metadata = { title: '数据可视化 · 股票与因子看板', description: '自由选择股票、因子和历史区间，用折线、柱状、面积与散点图组合可保存的研究看板。' };

export default function Page() { return <VisualizationWorkbench />; }

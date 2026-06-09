import type { ConsolePageConfig } from '../lib/researchConsoleData';

type Props = {
  config: ConsolePageConfig;
};

export function ArtifactStatusCard({ config }: Props) {
  return (
    <div className="artifact-card" data-mode={config.dataMode}>
      <div className="artifact-card__topline">
        <span className="badge">{config.eyebrow}</span>
        <span className="status-pill">{config.status}</span>
      </div>
      <h2>{config.title}</h2>
      <p>{config.description}</p>
      <dl className="meta-grid">
        <div><dt>API</dt><dd>{config.apiPath}</dd></div>
        <div><dt>Artifact</dt><dd>{config.artifact}</dd></div>
        <div><dt>data_mode</dt><dd>{config.dataMode}</dd></div>
      </dl>
      <div className="field-list">
        {config.fields.map((field) => <span key={field}>{field}</span>)}
      </div>
    </div>
  );
}

"""
JavaScript code for D3.js graph visualization and interactivity
"""


def get_complete_javascript():
    """Returns all JavaScript code as a single string"""
    return f"""
        {get_helper_functions()}
        {get_d3_visualization()}
        {get_event_handlers()}
        {get_tab_functions()}
        {get_utility_functions()}

        // Initialize
        generateLegend();
    """


def get_helper_functions():
    """Utility functions for notifications, colors, and legend generation"""
    return """
        // Notification system
        function showNotification(message) {
            const notification = document.getElementById('notification');
            notification.textContent = message;
            notification.classList.add('show');
            setTimeout(() => {
                notification.classList.remove('show');
            }, 3000);
        }

        // Color function based on node structure
        function getNodeColor(node) {
            const parts = node.label.split('.');
            let colorBasis = '';

            if (parts.length === 3) {
                const domain = parts[0];
                const dataset = parts[1];

                const allSameDomain = graphData.nodes.every(n => {
                    const nParts = n.label.split('.');
                    return nParts[0] === domain;
                });

                if (allSameDomain) {
                    colorBasis = dataset;
                } else {
                    colorBasis = domain;
                }
            } else if (parts.length === 2) {
                const domain = parts[0];

                const allSameDomain = graphData.nodes.every(n => {
                    const nParts = n.label.split('.');
                    return nParts[0] === domain;
                });

                if (allSameDomain) {
                    colorBasis = parts[1];
                } else {
                    colorBasis = domain;
                }
            } else {
                colorBasis = node.label;
            }

            const hash = Array.from(colorBasis).reduce((acc, char) => {
                return char.charCodeAt(0) + ((acc << 5) - acc);
            }, 0);
            const hue = Math.abs(hash % 360);
            return `hsl(${hue}, 70%, 85%)`;
        }

        // Generate dynamic legend based on unique databases
        function generateLegend() {
            const legendPanel = document.getElementById('legend-panel');
            if (!legendPanel) return;

            const colorGroups = new Map();
            let colorBasisType = 'Database';

            const databases = new Set();
            graphData.nodes.forEach(node => {
                const parts = node.label.split('.');
                if (parts.length > 0) {
                    databases.add(parts[0]);
                }
            });

            const allSameDatabase = databases.size === 1;

            if (allSameDatabase) {
                graphData.nodes.forEach(node => {
                    const parts = node.label.split('.');
                    let groupKey = '';

                    if (parts.length === 3) {
                        groupKey = parts[1];
                        colorBasisType = 'Schema/Dataset';
                    } else if (parts.length === 2) {
                        groupKey = parts[1];
                        colorBasisType = 'Element';
                    } else {
                        groupKey = parts[0];
                        colorBasisType = 'Node';
                    }

                    if (!colorGroups.has(groupKey)) {
                        colorGroups.set(groupKey, []);
                    }
                    colorGroups.get(groupKey).push(node);
                });
            } else {
                graphData.nodes.forEach(node => {
                    const parts = node.label.split('.');
                    const database = parts[0];

                    if (!colorGroups.has(database)) {
                        colorGroups.set(database, []);
                    }
                    colorGroups.get(database).push(node);
                });
                colorBasisType = 'Database';
            }

            let legendHtml = `
                <div class="legend-title">Legends (by ${colorBasisType})</div>
                <div class="legend-content">
            `;

            Array.from(colorGroups.keys()).sort().forEach(groupKey => {
                const sampleNode = colorGroups.get(groupKey)[0];
                const color = getNodeColor(sampleNode);

                legendHtml += `
                    <div class="legend-item">
                        <div class="legend-color" style="background-color: ${color};"></div>
                        <div class="legend-label">
                            <strong>${groupKey}</strong>
                        </div>
                    </div>
                `;
            });

            legendHtml += '</div>';
            legendPanel.innerHTML = legendHtml;
        }
    """


def get_d3_visualization():
    """D3.js code for creating and rendering the graph"""
    return """
        // Calculate layout dimensions
        const nodesPerLevel = {};
        graphData.nodes.forEach(node => {
            if (!nodesPerLevel[node.level]) {
                nodesPerLevel[node.level] = 0;
            }
            nodesPerLevel[node.level]++;
        });

        const maxNodesInLevel = Math.max(...Object.values(nodesPerLevel));
        const levels = Object.keys(nodesPerLevel).length;

        const nodeWidth = 250;
        const nodeHeight = 60;
        const horizontalSpacing = 400;
        const verticalSpacing = 200;
        const svgWidth = Math.max(window.innerWidth, maxNodesInLevel * horizontalSpacing + 200);
        const svgHeight = Math.max(window.innerHeight, levels * verticalSpacing + 200);

        // Create SVG
        const svg = d3.select("#svg-wrapper")
            .append("svg")
            .attr("width", svgWidth)
            .attr("height", svgHeight);

        // Add arrow markers
        const defs = svg.append("defs");

        defs.append("marker")
            .attr("id", "arrowhead")
            .attr("viewBox", "0 -5 10 10")
            .attr("refX", 8)
            .attr("refY", 0)
            .attr("markerWidth", 6)
            .attr("markerHeight", 6)
            .attr("orient", "auto")
            .append("path")
            .attr("d", "M0,-5L10,0L0,5")
            .attr("fill", "#546E7A");

        defs.append("marker")
            .attr("id", "arrowhead-highlighted")
            .attr("viewBox", "0 -5 10 10")
            .attr("refX", 8)
            .attr("refY", 0)
            .attr("markerWidth", 6)
            .attr("markerHeight", 6)
            .attr("orient", "auto")
            .append("path")
            .attr("d", "M0,-5L10,0L0,5")
            .attr("fill", "#FF6B6B");

        const container = svg.append("g");

        // Position nodes by level
        const levelGroups = {};
        graphData.nodes.forEach(node => {
            if (!levelGroups[node.level]) {
                levelGroups[node.level] = [];
            }
            levelGroups[node.level].push(node);
        });

        Object.keys(levelGroups).forEach(level => {
            const nodes = levelGroups[level];
            const levelY = parseInt(level) * verticalSpacing + 100;
            const totalWidth = nodes.length * horizontalSpacing;
            const startX = (svgWidth - totalWidth) / 2;

            nodes.forEach((node, index) => {
                node.x = startX + (index * horizontalSpacing) + horizontalSpacing / 2;
                node.y = levelY;
                node.fx = node.x;
                node.fy = node.y;
            });
        });

        // Create link references
        graphData.links.forEach(link => {
            link.sourceNode = graphData.nodes.find(n => n.id === link.source);
            link.targetNode = graphData.nodes.find(n => n.id === link.target);
        });

        // Create links
        const link = container.append("g")
            .selectAll("path")
            .data(graphData.links)
            .enter()
            .append("path")
            .attr("class", "link")
            .style("stroke", "#546E7A")
            .style("stroke-width", "2px")
            .style("fill", "none")
            .attr("marker-end", "url(#arrowhead)")
            .attr("d", d => {
                if (d.sourceNode && d.targetNode) {
                    const sx = d.sourceNode.x;
                    const sy = d.sourceNode.y + nodeHeight / 2;
                    const tx = d.targetNode.x;
                    const ty = d.targetNode.y - nodeHeight / 2;
                    const midY = (sy + ty) / 2;
                    return `M${sx},${sy} C${sx},${midY} ${tx},${midY} ${tx},${ty}`;
                }
                return "";
            });

        // Create nodes
        const node = container.append("g")
            .selectAll("g")
            .data(graphData.nodes)
            .enter()
            .append("g")
            .attr("class", "node")
            .attr("transform", d => `translate(${d.x},${d.y})`)
            .on("click", nodeClicked);

        node.append("rect")
            .attr("class", "node-rect")
            .attr("width", nodeWidth)
            .attr("height", nodeHeight)
            .attr("x", -nodeWidth / 2)
            .attr("y", -nodeHeight / 2)
            .attr("fill", d => getNodeColor(d))
            .attr("stroke", "#0277BD")
            .attr("stroke-width", 2);

        node.append("text")
            .attr("class", "node-text")
            .attr("text-anchor", "middle")
            .attr("y", -8)
            .text(d => {
                const label = d.label;
                return label.length > 35 ? label.substring(0, 32) + "..." : label;
            })
            .append("title")
            .text(d => d.label);

        node.append("text")
            .attr("class", "node-level")
            .attr("text-anchor", "middle")
            .attr("y", 10)
            .text(d => `Level ${d.level}`);
    """


def get_event_handlers():
    """Event handlers for node clicks, exploration, and metadata display"""
    return """
        // Node click handler
        function nodeClicked(event, d) {
            event.stopPropagation();
            showDataPanel(d);
        }

        // Show data panel
// Show data panel
function showDataPanel(node) {
    const panel = document.getElementById("data-panel-container");
    const nodeNameDisplay = document.getElementById("node-name-display");
    const graphContainer = document.getElementById("graph-container");

    window.currentNode = node;

    // Show panel
    panel.classList.add("visible");
    graphContainer.classList.add("with-panel");
    nodeNameDisplay.textContent = node.label;

    // NEW: Auto-center the graph on the clicked node
    centerGraphOnNode(node);

    // Load samples tab by default
    showSamplesTab(node);
}
function centerGraphOnNode(node) {
    const graphContainer = document.getElementById("graph-container");
    const svgWrapper = document.getElementById("svg-wrapper");
    
    // Get the container dimensions
    const containerWidth = graphContainer.clientWidth;
    const containerHeight = graphContainer.clientHeight;
    
    // Calculate scroll position to center the node
    // Account for node position and container size
    const scrollLeft = node.x - (containerWidth / 2);
    const scrollTop = node.y - (containerHeight / 2);
    
    // Smooth scroll to center
    graphContainer.scrollTo({
        left: Math.max(0, scrollLeft),
        top: Math.max(0, scrollTop),
        behavior: 'smooth'
    });
}

        function closeDataPanel() {
            const panel = document.getElementById("data-panel-container");
            const graphContainer = document.getElementById("graph-container");
            panel.classList.remove("visible");
            graphContainer.classList.remove("with-panel");
        }

        function clearHighlights() {
            closeDataPanel();
        }

        // Explore node
        function exploreNode(nodeLabel) {
            console.log('Exploring node:', nodeLabel);

            const parts = nodeLabel.split('.');
            let domain = '';
            let dataset = '';
            let element = '';

            if (parts.length === 3) {
                domain = parts[0];
                dataset = parts[1];
                element = parts[2];
            } else if (parts.length === 2) {
                domain = parts[0];
                element = parts[1];
            } else {
                element = parts[0];
            }

            const baseUrl = window.location.origin;
            const params = new URLSearchParams();
            params.set('explore_domain', domain);
            params.set('explore_dataset', dataset);
            params.set('explore_element', element);
            params.set('auto_trace', '1');
            const newUrl = baseUrl + '?' + params.toString();

            window.open(newUrl, '_blank');
        }
    """


def get_tab_functions():
    """Functions for tab switching and content display"""
    return """
function switchTab(tabName) {
    document.querySelectorAll('.tab').forEach(tab => {
        tab.classList.remove('active');
    });
    event.target.classList.add('active');

    const contentDiv = document.getElementById('tab-content');
    const node = window.currentNode;

    if (tabName === 'samples') {
        showSamplesTab(node);
    } else if (tabName === 'lineage') {
        showLineageTab(node);
    }
}

        function showSamplesTab(node) {
    const contentDiv = document.getElementById('tab-content');
    const sampleData = graphData.samples[node.label] || { adls: [], snowflake: [], databricks: [] };

    let html = '';

    // Find upstream node for comparison
    let upstreamNode = null;
    let upstreamData = { adls: [], snowflake: [], databricks: [] };
    
    const upstreamLinks = graphData.links.filter(l => {
        const targetId = typeof l.target === 'object' ? l.target.id : l.target;
        return targetId === node.id;
    });

    if (upstreamLinks.length > 0 && node.level > 0) {
        upstreamNode = graphData.nodes.find(n => {
            const sourceId = typeof upstreamLinks[0].source === 'object' ? upstreamLinks[0].source.id : upstreamLinks[0].source;
            return n.id === sourceId;
        });

        if (upstreamNode) {
            upstreamData = graphData.samples[upstreamNode.label] || { adls: [], snowflake: [], databricks: [] };
        }
    }
    
    // Get samples from any available source (priority: ADLS > Snowflake > Databricks)
    function getSamplesFromAnySource(data) {
        if (data.adls && data.adls.length > 0) return { samples: data.adls, source: 'ADLS', count: data.adls_count || data.adls.length };
        if (data.snowflake && data.snowflake.length > 0) return { samples: data.snowflake, source: 'Snowflake', count: data.snowflake_count || data.snowflake.length };
        if (data.databricks && data.databricks.length > 0) return { samples: data.databricks, source: 'Databricks', count: data.databricks_count || data.databricks.length };
        return { samples: [], source: null, count: 0 };
    }
    
    const currentSamples = getSamplesFromAnySource(sampleData);
    const upstreamSamples = getSamplesFromAnySource(upstreamData);
    
    // Check if upstream node exists (regardless of sample data)
    const hasUpstreamNode = upstreamNode && node.level > 0;
    // Check if upstream node has sample data (for comparison)
    const hasUpstreamData = hasUpstreamNode && upstreamSamples.samples.length > 0;
    
    // Level Context Header - Show for ALL nodes with upstream, not just ones with data
    if (hasUpstreamNode) {
        html += `
            <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #0078D4;">
                <div style="display: flex; align-items: center; justify-content: space-between; gap: 20px;">
                    <div style="flex: 1;">
                        <div style="font-size: 11px; color: #666; font-weight: 600; margin-bottom: 4px;">SOURCE (Level ${upstreamNode.level})</div>
                        <div style="font-family: 'Courier New', monospace; font-size: 12px; color: #333; font-weight: 600;">${upstreamNode.label}</div>
                    </div>
<div style="color: #0078D4; font-size: 20px; font-weight: bold; flex-shrink: 0;">-></div>
                    <div style="flex: 1;">
                        <div style="font-size: 11px; color: #666; font-weight: 600; margin-bottom: 4px;">TARGET (Level ${node.level})</div>
                        <div style="font-family: 'Courier New', monospace; font-size: 12px; color: #333; font-weight: 600;">${node.label}</div>
                    </div>
                </div>
            </div>
        `;
        
            
    } else {
        // Single node view - only for root nodes (level 0)
        html += `
            <div style="background: #f8f9fa; padding: 12px 15px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #6c757d;">
                <div style="font-size: 11px; color: #666; font-weight: 600; margin-bottom: 4px;">NODE (Level ${node.level})</div>
                <div style="font-family: 'Courier New', monospace; font-size: 12px; color: #333; font-weight: 600;">${node.label}</div>
            </div>
        `;
    }

    // Check if we have any data - but always keep the header visible
    if (currentSamples.samples.length === 0) {
        html += '<div style="padding: 20px; text-align: center; color: #999;">No sample data available</div>';
        contentDiv.innerHTML = html;
        return;
    }

    // Unified Comparison Section - Show data source flag at the top
    html += '<div style="margin-bottom: 25px;">';
    
    // Data Source Flag - Using same styling as SOURCE/TARGET header
    if (hasUpstreamData) {
        const sourceLabel = upstreamSamples.source || 'Unknown';
        const targetLabel = currentSamples.source || 'Unknown';
        html += `
            <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #0078D4;">
                <div style="display: flex; align-items: center; justify-content: space-between; gap: 20px;">
                    <div style="flex: 1;">
                        <div style="font-size: 11px; color: #666; font-weight: 600; margin-bottom: 4px;">SOURCE</div>
                        <div style="font-family: 'Courier New', monospace; font-size: 12px; color: #333; font-weight: 600;">${sourceLabel}</div>
                    </div>
                    <div style="color: #0078D4; font-size: 20px; font-weight: bold; flex-shrink: 0;">-></div>
                    <div style="flex: 1;">
                        <div style="font-size: 11px; color: #666; font-weight: 600; margin-bottom: 4px;">TARGET</div>
                        <div style="font-family: 'Courier New', monospace; font-size: 12px; color: #333; font-weight: 600;">${targetLabel}</div>
                    </div>
                </div>
            </div>
        `;
    } else {
        html += `
            <div style="background: #f8f9fa; padding: 12px 15px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #6c757d;">
                <div style="font-size: 11px; color: #666; font-weight: 600; margin-bottom: 4px;">DATA SOURCE</div>
                <div style="font-family: 'Courier New', monospace; font-size: 12px; color: #333; font-weight: 600;">${currentSamples.source || 'Unknown'}</div>
            </div>
        `;
    }
    
    // Total count
    html += `<div style="display: flex; align-items: center; gap: 10px; margin-bottom: 15px;">`;
    html += `<span style="background: #e9ecef; color: #495057; padding: 4px 12px; border-radius: 12px; font-size: 11px; font-weight: 600;">Total: ${currentSamples.count} rows</span>`;
    html += '</div>';

    // Show comparison if we have upstream data
    if (hasUpstreamData) {
        const maxLength = Math.max(currentSamples.samples.length, upstreamSamples.samples.length);
        
        for (let i = 0; i < Math.min(5, maxLength); i++) {
            const source = upstreamSamples.samples[i] || '';
            const target = currentSamples.samples[i] || '';
            
            // Determine status
            let statusColor = 'white';
            let statusBorder = '#17a2b8';
            let statusText = 'NEW';
            
            if (source && target) {
                if (source === target) {
                    statusColor = 'white';
                    statusBorder = '#28a745';
                    statusText = 'UNCHANGED';
                } else {
                    statusColor = 'white';
                    statusBorder = '#ffc107';
                    statusText = 'CHANGED';
                }
            }

            html += `
                <div style="display: flex; align-items: center; margin: 6px 0; font-family: 'Courier New', monospace; font-size: 12px; padding: 8px; background: ${statusColor}; border-left: 3px solid ${statusBorder}; border-radius: 4px;">
                    <span style="color: #495057; flex: 1; font-weight: 600;">${source || '(empty)'}</span>
                    <span style="color: #999; margin: 0 12px; font-weight: bold;">-></span>
                    <span style="color: #495057; flex: 1; font-weight: 600;">${target || '(empty)'}</span>
                    <span style="background: ${statusBorder}; color: white; padding: 2px 8px; border-radius: 10px; font-size: 10px; font-weight: bold; margin-left: 10px; flex-shrink: 0;">${statusText}</span>
                </div>
            `;
        }
    } else {
        // Just show current node samples without comparison
        currentSamples.samples.slice(0, 5).forEach(s => {
            html += `
                <div style="padding: 8px; background: white; border: 1px solid #e9ecef; border-radius: 4px; margin: 6px 0;">
                    <span style="font-family: 'Courier New', monospace; font-size: 12px; font-weight: 600; color: #495057;">${s}</span>
                </div>
            `;
        });
    }
    html += '</div>';

    html += `
        <div style="margin-top: 20px; padding-top: 15px; border-top: 1px solid #dee2e6; display: flex; gap: 10px;">
            <button class="control-btn" onclick="downloadFullData('${node.label}')" 
                    style="background: white; color: #0078D4; border: 2px solid #0078D4; margin: 0; flex: 1;">
                Download CSV
            </button>
            <button class="control-btn" onclick="exploreNode('${node.label}')" 
                    style="background: white; color: #0078D4; border: 2px solid #0078D4; margin: 0; flex: 1;">
                Explore This Node
            </button>
        </div>
    `;

    contentDiv.innerHTML = html;
}

        function showLineageTab(node) {
            const contentDiv = document.getElementById('tab-content');

            const upstreamLinks = graphData.links.filter(l => {
                const targetId = typeof l.target === 'object' ? l.target.id : l.target;
                return targetId === node.id;
            });

            const downstreamLinks = graphData.links.filter(l => {
                const sourceId = typeof l.source === 'object' ? l.source.id : l.source;
                return sourceId === node.id;
            });

            let html = '<div style="margin-bottom: 15px;"><strong>Upstream Sources:</strong></div>';

            if (upstreamLinks.length > 0) {
                upstreamLinks.forEach(link => {
                    const sourceNode = graphData.nodes.find(n => n.id === (typeof link.source === 'object' ? link.source.id : link.source));
                    html += `
                        <div class="upstream-item">
                            <div style="font-family: monospace; font-size: 12px;">${sourceNode.label}</div>
                            <div style="font-size: 11px; color: #666; margin-top: 4px;">Level ${sourceNode.level}</div>
                        </div>
                    `;
                });
            } else {
                html += '<div style="color: #999; font-style: italic;">No upstream sources</div>';
            }

            html += '<div style="margin: 20px 0 15px 0;"><strong>Downstream Targets:</strong></div>';

            if (downstreamLinks.length > 0) {
                downstreamLinks.forEach(link => {
                    const targetNode = graphData.nodes.find(n => n.id === (typeof link.target === 'object' ? link.target.id : link.target));
                    html += `
                        <div class="downstream-item">
                            <div style="font-family: monospace; font-size: 12px;">${targetNode.label}</div>
                            <div style="font-size: 11px; color: #666; margin-top: 4px;">Level ${targetNode.level}</div>
                        </div>
                    `;
                });
            } else {
                html += '<div style="color: #999; font-style: italic;">No downstream targets</div>';
            }

            contentDiv.innerHTML = html;
        }
        
    """


def get_utility_functions():
    """Additional utility functions"""
    return """
        async function downloadFullData(nodeLabel) {
            const sampleData = graphData.samples[nodeLabel] || {};

            let csvContent = "source,value\\n";

            (sampleData.adls || []).forEach(val => {
                csvContent += `ADLS,"${val}"\\n`;
            });

            (sampleData.snowflake || []).forEach(val => {
                csvContent += `Snowflake,"${val}"\\n`;
            });

            (sampleData.databricks || []).forEach(val => {
                csvContent += `Databricks,"${val}"\\n`;
            });

            const blob = new Blob([csvContent], { type: 'text/csv' });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${nodeLabel.replace(/\\./g, '_')}_samples.csv`;
            a.click();
            window.URL.revokeObjectURL(url);
        }
    """

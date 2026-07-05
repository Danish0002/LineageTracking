"""
HTML template and CSS styles for the graph visualization
"""


def build_graph_html(graph_json):
    """
    Builds the complete HTML document for graph rendering

    Args:
        graph_json: JSON string containing nodes, links, and samples data

    Returns:
        Complete HTML string ready for rendering
    """
    return f"""
<!DOCTYPE html>
<html>
<head>
    {get_html_head()}
    {get_css_styles()}
</head>
<body>
    {get_html_body()}
    {get_javascript_section(graph_json)}
</body>
</html>
"""


def get_html_head():
    """Returns the HTML head section with meta tags and D3.js import"""
    return """
    <meta charset="utf-8">
    <title>Interactive Lineage Graph</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
"""


def get_css_styles():
    """Returns all CSS styles for the graph visualization"""
    return """
    <style>
        body {
            margin: 0;
            padding: 0;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }

        /* Graph container - full width initially */
        #graph-container {
            width: 100%;
            height: 100vh;
            background: white;
            position: relative;
            overflow: auto;
        }

        /* When data panel is open, adjust layout */
        #graph-container.with-panel {
            width: 40%;
            float: left;
        }

        #svg-wrapper {
            min-width: 100%;
            min-height: 100%;
        }

        /* Data Panel - slides in from right */
        #data-panel-container {
            position: fixed;
            top: 0;
            right: -60%;
            width: 60%;
            height: 100vh;
            background: white;
            box-shadow: -4px 0 16px rgba(0,0,0,0.15);
            overflow-y: auto;
            padding: 30px;
            box-sizing: border-box;
            transition: right 0.3s ease-in-out;
            z-index: 2000;
        }

        #data-panel-container.visible {
            right: 0;
        }

        /* Close button for data panel */
        .close-panel-btn {
    position: absolute;
    top: 20px;
    right: 20px;
    background: transparent;
    color: #999;
    border: none;
    width: 24px;
    height: 24px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 20px;
    line-height: 1;
    z-index: 10;
    transition: all 0.2s;
}

.close-panel-btn:hover {
    background: #f0f0f0;
    color: #333;
}

        /* Sample Data Cards */
        /* Sample Data Cards - Minimal Design */
.sample-card {
    background: white !important;
    color: #333;
    padding: 20px;
    border-radius: 8px;
    margin-bottom: 16px;
    border: 1px solid #dee2e6;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}

.sample-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 15px;
    padding-bottom: 10px;
    border-bottom: 1px solid #dee2e6;
    background: transparent;
}

.sample-badge {
    background: #e9ecef;
    color: #495057;
    padding: 4px 12px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 600;
}

.sample-values {
    background: white;
    padding: 12px;
    border-radius: 6px;
    font-family: 'Courier New', monospace;
    font-size: 13px;
    line-height: 1.8;
    color: #495057;
    border: 1px solid #e9ecef;
    font-weight: 600;
}

.sample-values div {
    margin: 6px 0;
}

        /* Tabs */
        .tabs {
            display: flex;
            gap: 0;
            margin-bottom: 25px;
            border-bottom: 3px solid #e0e0e0;
        }

        .tab {
            flex: 1;
            padding: 15px 20px;
            background: transparent;
            border: none;
            border-bottom: 3px solid transparent;
            cursor: pointer;
            font-size: 15px;
            font-weight: 600;
            color: #666;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }

        .tab.active {
            color: #0078D4;
            border-bottom: 3px solid #0078D4;
            background: linear-gradient(180deg, transparent 0%, rgba(0,120,212,0.05) 100%);
        }

        .tab:hover {
            color: #0078D4;
            background: rgba(0,120,212,0.03);
        }

        /* Action Buttons */
        .action-buttons {
            display: flex;
            gap: 10px;
            margin-top: 25px;
            padding-top: 25px;
            border-top: 2px solid #e9ecef;
        }

        .btn-primary {
            flex: 1;
            padding: 14px 24px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-weight: bold;
            cursor: pointer;
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
            transition: transform 0.2s, box-shadow 0.2s;
        }

        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
        }

        /* Data Panel Header */
        .data-panel-header {
            margin-bottom: 20px;
            padding-bottom: 20px;
            border-bottom: 2px solid #e9ecef;
        }

        .data-panel-title {
            font-size: 18px;
            font-weight: bold;
            color: #0078D4;
            margin-bottom: 10px;
        }

        .data-panel-subtitle {
            font-size: 13px;
            color: #666;
            font-family: monospace;
            word-break: break-all;
        }

        /* Node styles */
        .node {
            cursor: pointer;
            transition: all 0.3s ease;
        }
        .node:hover {
            filter: brightness(0.9);
        }
        .node-rect {
            stroke-width: 2px;
            rx: 8;
            ry: 8;
        }
        .node-text {
            pointer-events: none;
            user-select: none;
            font-size: 11px;
            fill: #333;
        }
        .node-level {
            pointer-events: none;
            user-select: none;
            font-size: 10px;
            fill: #666;
            font-weight: bold;
        }
        .link {
            fill: none;
            stroke: #546E7A;
            stroke-width: 2px;
        }
        .link.highlighted {
            stroke: #FF6B6B;
            stroke-width: 3px;
        }

        /* Controls */
        .controls {
            position: fixed;
            top: 20px;
            right: 20px;
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
            z-index: 1000;
        }

        .control-btn {
            display: block;
            width: 100%;
            padding: 8px 16px;
            margin: 5px 0;
            background: #0078D4;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 13px;
            font-weight: 600;
        }

        .control-btn:hover {
            background: #005a9e;
        }

        /* Legend */
        /* Legend */
        .legend-panel {
            position: fixed;
            bottom: 20px;
            left: 20px;
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
            max-width: 220px;
            max-height: 300px;
            overflow-x: auto;
            overflow-y: auto;
            z-index: 1000;
        }

        .legend-title {
            font-size: 14px;
            font-weight: bold;
            margin-bottom: 12px;
            color: #333;
            border-bottom: 2px solid #e0e0e0;
            padding-bottom: 6px;
        }

        .legend-content {
            display: flex;
            flex-direction: column;
            gap: 12px;
        }

        .legend-item {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .legend-color {
            width: 30px;
            height: 30px;
            border-radius: 6px;
            flex-shrink: 0;
        }

        .legend-label {
            font-size: 12px;
            line-height: 1.4;
            color: #333;
        }

        /* Notification */
        .notification {
            position: fixed;
            top: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: #0078D4;
            color: white;
            padding: 12px 24px;
            border-radius: 6px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
            z-index: 3000;
            display: none;
            font-weight: 600;
        }

        .notification.show {
            display: block;
        }

        /* Lineage items */
        .upstream-item, .downstream-item {
            margin: 10px 0;
            padding: 10px;
            background: #f8f9fa;
            border-left: 3px solid #0078D4;
            border-radius: 4px;
        }
    </style>
"""


def get_html_body():
    """Returns the HTML body structure"""
    return """
    <div id="notification" class="notification"></div>

    <div id="graph-container">
        <div id="svg-wrapper"></div>
    </div>


        <div id="legend-panel" class="legend-panel"></div>

    <div id="data-panel-container">
        <button class="close-panel-btn" onclick="closeDataPanel()">×</button>

        <div class="data-panel-header">
            <div class="data-panel-title">Node Details</div>
            <div class="data-panel-subtitle" id="node-name-display"></div>
        </div>

        <div class="tabs">
    <button class="tab active" onclick="switchTab('samples')">Samples</button>
    <button class="tab" onclick="switchTab('lineage')">Lineage</button>
</div>

        <div id="tab-content" class="tab-content">
            <!-- Content loads here -->
        </div>
    </div>
"""



def get_javascript_section(graph_json):
    """
    Returns the complete JavaScript section

    Args:
        graph_json: JSON string containing graph data
    """
    from .javascript import get_complete_javascript

    return f"""
    <script>
        const graphData = {graph_json};
        {get_complete_javascript()}
    </script>
"""
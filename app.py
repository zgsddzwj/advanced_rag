"""
Admin 后台 - PDF 解析管理系统
提供 Web 界面，支持上传文档、解析并查看结果
"""

import os
import json
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, flash
from werkzeug.utils import secure_filename
import uuid

from langchain_parser import LangChainPDFParser
from config import Config

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here-change-in-production'
app.config['UPLOAD_FOLDER'] = Config.PROJECT_ROOT / 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size
app.config['ALLOWED_EXTENSIONS'] = {'pdf'}

# 创建必要目录
app.config['UPLOAD_FOLDER'].mkdir(parents=True, exist_ok=True)
Config.init_directories()


def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def get_parse_history():
    """获取解析历史记录"""
    history_file = Config.OUTPUT_DIR / 'parse_history.json'
    if history_file.exists():
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []


def save_parse_history(record):
    """保存解析历史记录"""
    history_file = Config.OUTPUT_DIR / 'parse_history.json'
    history = get_parse_history()
    history.insert(0, record)  # 最新的在前面
    # 只保留最近50条记录
    history = history[:50]
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


@app.route('/')
def index():
    """首页 - 显示上传界面和解析历史"""
    history = get_parse_history()
    return render_template('index.html', history=history[:10])  # 显示最近10条


@app.route('/upload', methods=['POST'])
def upload_file():
    """上传并解析 PDF 文件"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': '没有文件被上传'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': '文件名为空'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'success': False, 'error': '只支持 PDF 文件'}), 400
    
    try:
        # 生成唯一文件名
        unique_id = str(uuid.uuid4())[:8]
        original_filename = secure_filename(file.filename)
        filename = f"{unique_id}_{original_filename}"
        filepath = app.config['UPLOAD_FOLDER'] / filename
        
        # 保存文件
        file.save(str(filepath))
        
        # 解析 PDF
        parser = LangChainPDFParser(
            output_dir=str(Config.OUTPUT_DIR),
            enable_monitoring=True,
            enable_progress=False  # Web 环境下不显示进度条
        )
        
        result = parser.parse_pdf(
            pdf_path=str(filepath),
            output_filename=f"{unique_id}_{Path(original_filename).stem}",
            show_preview=False  # Web 环境下不显示预览
        )
        
        if result['status'] == 'success':
            # 保存解析记录
            record = {
                'id': unique_id,
                'original_filename': original_filename,
                'upload_time': datetime.now().isoformat(),
                'parse_status': 'success',
                'stats': result.get('stats', {}),
                'output_files': result.get('output_files', {}),
                'file_size': filepath.stat().st_size
            }
            save_parse_history(record)
            
            return jsonify({
                'success': True,
                'id': unique_id,
                'original_filename': original_filename,
                'result': {
                    'stats': result.get('stats', {}),
                    'metadata': result.get('metadata', {}),
                    'text_preview': result.get('text_content', '')[:1000],  # 前1000字符
                    'pages_count': len(result.get('pages_info', [])),
                    'output_files': result.get('output_files', {})
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', '解析失败')
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/result/<file_id>')
def view_result(file_id):
    """查看解析结果详情"""
    history = get_parse_history()
    record = next((r for r in history if r['id'] == file_id), None)
    
    if not record:
        flash('找不到解析记录', 'error')
        return redirect(url_for('index'))
    
    # 读取解析结果
    output_filename = record['output_files'].get('json', '').replace('_info.json', '')
    json_file = Config.OUTPUT_DIR / 'structured' / f"{Path(output_filename).name}_info.json"
    text_file = Config.OUTPUT_DIR / 'text' / f"{Path(output_filename).name}.txt"
    
    result_data = {}
    if json_file.exists():
        with open(json_file, 'r', encoding='utf-8') as f:
            result_data = json.load(f)
    
    text_content = ''
    if text_file.exists():
        with open(text_file, 'r', encoding='utf-8') as f:
            text_content = f.read()
    
    return render_template('result.html', 
                         record=record, 
                         result_data=result_data,
                         text_content=text_content)


@app.route('/api/result/<file_id>')
def get_result(file_id):
    """API: 获取解析结果"""
    history = get_parse_history()
    record = next((r for r in history if r['id'] == file_id), None)
    
    if not record:
        return jsonify({'error': '找不到解析记录'}), 404
    
    # 读取完整结果
    output_filename = record['output_files'].get('json', '').replace('_info.json', '')
    json_file = Config.OUTPUT_DIR / 'structured' / f"{Path(output_filename).name}_info.json"
    text_file = Config.OUTPUT_DIR / 'text' / f"{Path(output_filename).name}.txt"
    
    result_data = {}
    if json_file.exists():
        with open(json_file, 'r', encoding='utf-8') as f:
            result_data = json.load(f)
    
    text_content = ''
    if text_file.exists():
        with open(text_file, 'r', encoding='utf-8') as f:
            text_content = f.read()
    
    return jsonify({
        'success': True,
        'record': record,
        'result': result_data,
        'text_content': text_content
    })


@app.route('/download/text/<file_id>')
def download_text(file_id):
    """下载文本文件"""
    history = get_parse_history()
    record = next((r for r in history if r['id'] == file_id), None)
    
    if not record:
        flash('找不到解析记录', 'error')
        return redirect(url_for('index'))
    
    text_file = Path(record['output_files'].get('text', ''))
    if text_file.exists():
        return send_file(str(text_file), as_attachment=True,
                        download_name=f"{Path(record['original_filename']).stem}.txt")
    else:
        flash('文件不存在', 'error')
        return redirect(url_for('index'))


@app.route('/download/json/<file_id>')
def download_json(file_id):
    """下载 JSON 文件"""
    history = get_parse_history()
    record = next((r for r in history if r['id'] == file_id), None)
    
    if not record:
        flash('找不到解析记录', 'error')
        return redirect(url_for('index'))
    
    json_file = Path(record['output_files'].get('json', ''))
    if json_file.exists():
        return send_file(str(json_file), as_attachment=True,
                        download_name=f"{Path(record['original_filename']).stem}_info.json")
    else:
        flash('文件不存在', 'error')
        return redirect(url_for('index'))


@app.route('/api/history')
def api_history():
    """API: 获取解析历史"""
    history = get_parse_history()
    return jsonify({'success': True, 'history': history})


if __name__ == '__main__':
    # macOS AirPlay Receiver 默认占用 5000 端口，改用 8080
    PORT = 8080
    
    print("=" * 70)
    print("🚀 PDF 解析 Admin 后台启动")
    print("=" * 70)
    print(f"📁 上传目录: {app.config['UPLOAD_FOLDER']}")
    print(f"📁 输出目录: {Config.OUTPUT_DIR}")
    print(f"🌐 访问地址: http://127.0.0.1:{PORT}")
    print(f"   或访问: http://localhost:{PORT}")
    print("=" * 70)
    print()
    
    app.run(debug=True, host='0.0.0.0', port=PORT)


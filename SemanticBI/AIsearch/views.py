from django.shortcuts import render, redirect, get_object_or_404
from django.core.files.storage import FileSystemStorage
from .services.ingestion import IngestionService
from .services.rag_engine import RAGEngine
from .services.clustering import ClusteringService
from .services.endee_client import EndeeClient
from .models import Dataset
import os
import logging

logger = logging.getLogger(__name__)

def upload_view(request):
    if request.method == 'POST' and request.FILES.get('dataset'):
        dataset_file = request.FILES['dataset']
        fs = FileSystemStorage()
        filename = fs.save(dataset_file.name, dataset_file)
        uploaded_file_url = fs.path(filename)
        
        logger.info(f"Received file upload: {dataset_file.name}")
        try:
            ingestion_service = IngestionService()
            # Pass the original filename to generate a unique index
            result = ingestion_service.process_dataset(uploaded_file_url, dataset_file.name)
            
            # Save dataset record in database
            new_dataset = Dataset.objects.create(
                name=dataset_file.name,
                file_path=uploaded_file_url,
                index_name=result['index_name'],
                total_rows=result['total_rows']
            )
            
            # Set as active dataset in session
            request.session['active_dataset_id'] = new_dataset.id
            request.session['dataset_uploaded'] = True
            request.session['active_index_name'] = new_dataset.index_name
            request.session['total_rows'] = new_dataset.total_rows
            
            logger.info(f"Successfully processed {result['total_rows']} rows. Index: {result['index_name']}")
            return render(request, 'AIsearch/upload.html', {
                'success': True,
                'total_rows': result['total_rows'],
                'dataset_name': new_dataset.name
            })
        except Exception as e:
            logger.error(f"Error processing upload: {str(e)}", exc_info=True)
            return render(request, 'AIsearch/upload.html', {
                'error': str(e)
            })
    
    # Check if already uploaded
    active_id = request.session.get('active_dataset_id')
    active_dataset = Dataset.objects.filter(id=active_id).first() if active_id else None
    
    context = {
        'is_uploaded': request.session.get('dataset_uploaded', False),
        'active_dataset': active_dataset,
        'total_rows': request.session.get('total_rows', 0)
    }
    return render(request, 'AIsearch/upload.html', context)

def history_view(request):
    datasets = Dataset.objects.all().order_by('-uploaded_at')
    return render(request, 'AIsearch/history.html', {'datasets': datasets})

def select_dataset_view(request, dataset_id):
    dataset = get_object_or_404(Dataset, id=dataset_id)
    request.session['active_dataset_id'] = dataset.id
    request.session['dataset_uploaded'] = True
    request.session['active_index_name'] = dataset.index_name
    request.session['total_rows'] = dataset.total_rows
    return redirect('search')

def search_view(request):
    if not request.session.get('dataset_uploaded'):
        return redirect('upload')
        
    index_name = request.session.get('active_index_name', 'business_records')
    query = request.GET.get('q')
    results = []
    if query:
        try:
            rag_engine = RAGEngine()
            results = rag_engine.retrieve_relevant_rows(query, index_name=index_name)
        except Exception as e:
            logger.error(f"Search error: {str(e)}")
    return render(request, 'AIsearch/search.html', {'results': results, 'query': query})

def insights_view(request):
    if not request.session.get('dataset_uploaded'):
        return redirect('upload')

    index_name = request.session.get('active_index_name', 'business_records')
    query = request.GET.get('q')
    insight = ""
    if query:
        try:
            rag_engine = RAGEngine()
            retrieved_rows = rag_engine.retrieve_relevant_rows(query, index_name=index_name)
            logger.info(f"Retrieved {len(retrieved_rows)} rows for insights from {index_name}")
            insight = rag_engine.generate_insight(query, retrieved_rows)
        except Exception as e:
            logger.error(f"Error generating insight: {str(e)}", exc_info=True)
            insight = f"Error generating insight: {str(e)}"
    return render(request, 'AIsearch/insights.html', {'insight': insight, 'query': query})

def analytics_view(request):
    if not request.session.get('dataset_uploaded'):
        return redirect('upload')
    
    index_name = request.session.get('active_index_name', 'business_records')
    try:
        rag_engine = RAGEngine()
        sample_results = rag_engine.retrieve_relevant_rows("general business records", index_name=index_name, top_k=50)
        
        if not sample_results:
            return render(request, 'AIsearch/analytics.html', {'error': 'No data found in active index.'})

        sector_counts = {}
        for row in sample_results:
            meta = row.get('metadata', {})
            for k, v in meta.items():
                if any(word in k.lower() for word in ['industry', 'category', 'sector', 'purpose']):
                    val = str(v).strip()
                    if val and val.lower() != 'nan':
                        sector_counts[val] = sector_counts.get(val, 0) + 1
        
        top_sectors = []
        sorted_sectors = sorted(sector_counts.items(), key=lambda x: x[1], reverse=True)[:4]
        for name, count in sorted_sectors:
            top_sectors.append({'name': name, 'value': count})
        
        high_sim = len([r for r in sample_results if r['score'] > 0.7])
        med_sim = len([r for r in sample_results if 0.4 <= r['score'] <= 0.7])
        low_sim = len([r for r in sample_results if r['score'] < 0.4])
        
        similarity_clusters = [
            {'label': 'High Similarity', 'density': high_sim},
            {'label': 'Medium Similarity', 'density': med_sim},
            {'label': 'Low Similarity', 'density': low_sim}
        ]

        analytics_data = {
            'total_indexed': request.session.get('total_rows', 0),
            'top_sectors': top_sectors if top_sectors else [{'name': 'General', 'value': 100}],
            'similarity_clusters': similarity_clusters
        }
        
        return render(request, 'AIsearch/analytics.html', {'data': analytics_data})
    except Exception as e:
        logger.error(f"Analytics error: {str(e)}", exc_info=True)
        return render(request, 'AIsearch/analytics.html', {'error': str(e)})

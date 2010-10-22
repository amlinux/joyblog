var post_id;
function reply(parent_id)
{
	var div = document.createElement('div');
	div.className = 'reply-comment c';
	div.innerHTML = '<form action="/posts/' + post_id + '/comments" method="post"><input type="hidden" name="parent_id" value="' + parent_id + '" /><div class="form-row"><div class="form-title">Текст комментария:</div><div class="form-control"><input id="reply-body' + post_id + '" name="body" size="50" /></div></div><div class="form-row"><div class="form-control"><input type="submit" value="Опубликовать" /></div></div></form>';
	var a = document.getElementById('reply-link' + parent_id);
	a.parentNode.replaceChild(div, a);
	document.getElementById('reply-body' + post_id).focus()
	return false;
}
